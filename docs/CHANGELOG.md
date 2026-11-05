# CHANGELOG — g360-erp-nc-sustentor

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
