# CHANGELOG — g360-erp-nc-sustentor

## [Unreleased] — Optimizaciones de performance (iteración 2)

### Performance

- **Opt 1 — Reporte de compras: una sola lectura SQL por cliente** (`06a7770`)
  - El export encadenaba 9 lecturas SQL por cliente (~20.35s); ahora hace 1 lectura
    y deriva el resto en pandas. Objetivo: <5s.
  - Switch `USAR_V2` con fallback a la v1.

- **Opt 2 — Expediente: historial de auditoría calculado una sola vez** (`4e9180b`)
  - Antes se re-filtraba 4 veces el mismo DataFrame en `_enriquecer_resultado`;
    ahora se calcula 1 vez y se inyecta a los helpers.

- **Opt 3A — Expediente: vectorizar 10 `iterrows` del pipeline de sustento** (`94d60c6`)
  - `iterrows` → `df.to_dict("records")` en AL12, `_mapear_num_a_docs` y los renders de Excel.

- **Opt 3B — Reporte de compras: vectorizar 11 `iterrows` del export** (`80b632c`)
  - `iterrows` → `df.to_dict("records")`.

### Changed

- **Opt 4 — Allowlist solo-b para NC/NDB** (`3de2bab`)
  - Regla nueva: la nota sigue a su factura — pasa solo si la factura referenciada
    tiene ≥1 línea activa. Se elimina el camino orphan-safe.
  - Impacto medido (auditoría sobre la DB real de 3.37 GB): de 173,382 NC/ND, dejan
    de pasar 4,239 (2.4%); el 96% son de 2010-2012 y ~16 notas recientes resultan afectadas.
  - El bloque "NC SIN FACTURA (REVISAR)" de la hoja Ajustes queda vacío con la allowlist
    activa — costo aceptado y documentado.
  - Motivo: las huérfanas reales son datos heredados del inicio del sistema; la regla
    nueva refleja la intención de negocio ("toda NC/ND nace de una factura").

### Fixed

- **Alineacion de la columna NC en `_df_det_v2`** - la lista de NC asociadas
  podia asignarse a filas de otra factura: el `sort_values(["FECHA", "DOC", "SKU"]` de
  arriba desordena el indice, y asignar `out["NC"] = pd.Series([...])` (indice implicito
  0..n-1) alineaba por ETIQUETA en lugar de por POSICION. Encontrado con la DB de
  produccion (cliente 00023307: 128 filas afectadas, la NC de F204-47353 aparecia en
  la fila de F204-47352). Asignacion posicional con `.to_numpy()` (regresion cubierta
  por `test_nc_asociadas_no_se_desalinea_tras_el_sort`).

### Verificación

```
uv run pytest -q
# 1793 passed, 0 failed
```

- `ruff` limpio.
- Tests de regresión nuevos para los cambios de comportamiento.

## 1.2.2 — Migración Flet 1.0.5 + Inspección Liviana

### Mejoras

- **Inspección liviana** (`capture_service.py:update_from_last`)
  - Cuando `MAX(fecha_orig) == hoy`, se compara conteo local vs portal antes de descargar
  - Si conteos coinciden → omite el día (no baja nada)
  - Si difieren → captura normalmente
  - Si falla cualquier paso → incluye hoy por seguridad
  - Ver `docs/inspeccion-liviana.md`

- **`IntranetClient.count_grid_rows()`**
  - Nuevo método: GET L0 que devuelve cantidad de filas sin descargar export
  - Base de la inspección liviana

### Correcciones

- **Header limpio** (`main.py:_build_header`)
  - Eliminados bloques de código duplicado (4 versiones del mismo return)
  - Función ahora tiene un solo bloque vivo

- **FilePicker migrado** (`main.py`)
  - Eliminado `_on_picker_generic`, `_picker_callback`, `_picker_files_callback`
  - Uso exclusivo de `page.run_task` + async `pick_files`
  - FilePicker como servicio en `page.services`

- **safe_handler migrado** (`src/core/g360_theme.py`)
  - Cambio de `page.snack_bar.open` a `page.show_dialog(SnackBar)`
  - Compatible con Flet 1.0.5

### Limpieza

- Eliminados artefactos de debug: `probe_*.py`, `smoke_db.py`, `*_err.txt`, logs
- Eliminados paneles placeholder vacíos: `src/ui/panels/gestion.py`, `busqueda.py`

### Estado de tests

```
uv run pytest -q
# 1725 passed, 13 warnings in ~6:20
```

Los warnings son de pandas (`future.no_silent_downcasting`) y no afectan funcionalidad.

## 1.2.1 — Migración Flet 0.28 → 1.0.5 (inicial)

- Migración completa de API Flet:
  - `ft.app()` → `ft.run()`
  - FilePicker como servicio
  - `SnackBar` via `show_dialog`
  - Clases `Padding`/`Border` capitalizadas
  - `BoxFit.CONTAIN`
  - `FilledButton`/`OutlinedButton`
  - `TabBarView` nativo

- Tests: 1725 passed
