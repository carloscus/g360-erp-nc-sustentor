# Pedido para `g360-ventas-db` (Tauri) — Fases F2/F3/F4

Este documento es el requerimiento que el repo Tauri debe cumplir para que
`sincronizar_desde_remota_parcial` deje de compensar lo que el productor no
garantiza. Está escrito desde la perspectiva del consumidor; cada invariante
tiene un test correspondiente en `tests/test_fixture_doradas.py` y en este
repo.

---

## Principio

El productor garantiza invariantes **al escribir**. El consumidor asume que
ya vienen cumplidas y nunca las re-valida (excepto como red de seguridad, no
como norma).

Si el consumidor tiene que normalizar algo que llega del productor, es un
bug del productor, no una característica del consumidor.

---

## F2: Invariantes al escribir

### 2.1 Fechas en ISO

| Campo | Formato | Cómo se valida |
|---|---|---|
| `fecha_orig` | `YYYY-MM-DD` | `CHECK(length(fecha_orig)=10 AND fecha_orig GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]')` |
| `fecha_ref` | `YYYY-MM-DD` o NULL | igual, nullable |
| `fecha_venc` | `YYYY-MM-DD` o NULL | igual, nullable |
| `fec_cargo` | `YYYY-MM-DD` o NULL | igual, nullable |

**Fixture dorada** (`tests/fixtures_doradas/fechas_crudas.json`): entrada con
`15/01/2024` → salida esperada `2024-01-15`. Ambos repos pasan la misma fixture.

### 2.2 `id_pedido` sin espacios

| Campo | Regla |
|---|---|
| `id_pedido` | `"_" .join(str(v).split())` al escribir |

**Fixture dorada** (`id_pedido_espacios.json`): entrada `"SADIE  25  X"` →
salida `"SADIE_25_X"`.

### 2.3 `mes_ref` canónico

| Campo | Regla |
|---|---|
| `mes_ref` | `substr(fecha_orig,1,7)` calculado al escribir |

**Fixture dorada** (`mes_ref_derivado.json`): entrada con `fecha_orig = "2024-01-15"` → salida `mes_ref = "2024-01"`.

### 2.4 Columnas generadas

Para evitar que el consumidor las calcule:

```sql
-- Opción A: GENERATED ALWAYS AS (stored)
mes_ref TEXT NOT NULL GENERATED ALWAYS AS (substr(fecha_orig, 1, 7)) STORED,
anho INTEGER NOT NULL GENERATED ALWAYS AS (CAST(substr(fecha_orig,1,4) AS INTEGER)) STORED,
mes INTEGER NOT NULL GENERATED ALWAYS AS (CAST(substr(fecha_orig,6,2) AS INTEGER)) STORED,
```

Si SQLite no lo soporta en la versión objetivo, calcular en el INSERT es
aceptable. Lo importante es que **el dato llegue calculado**, no que la DB lo
calcule.

### 2.5 `folio_unico` no vacío

Si `folio_unico` es NULL o vacío, calcularlo como:
```
tpo_doc || '/' || serie_doc || '/' || nro_doc
```
El consumidor confía en esta columna para deduplicar por documento. Si falta,
los pickers y el merge por folio se rompen.

---

## F3: Paquete de días (cartucho emitido por el productor)

El consumidor tiene `exportar_cartucho` + `_db_parcial`. Si el productor
emite el mismo artefacto, el consumidor elimina esa duplicación.

### 3.1 Formato del paquete

Un directorio (o ZIP) con:

```
historial.db          ← DB con schema completo, datos en rango, ÍndICES
                        construidos, sin derivados locales
CARTUCHO.json         ← manifiesto (ver §3.2)
config_sanitizado.json ← allowlist del emisor (vacía si es semilla)
```

El `historial.db` debe tener:
- Schema completo (`CREATE_TABLE_VENTAS` + `CREATE_AUDIT_TABLES` +
  `CREATE_DIM_TABLES` + `CREATE_FACT_TABLES` + índices).
- `PRAGMA user_version = <versión_contrato>`.
- `day_checksums` populado para el rango.
- `_migracion_*` marcado si aplica.

**Sin derivados locales**: `agg_cliente_mes`, `nc_asociadas`, `stats_cache`
no viajan (dependen de la allowlist del receptor).

### 3.2 Manifiesto (`CARTUCHO.json`)

```json
{
  "version": 3,
  "normalizacion_version": 1,
  "tipo": "semilla|trabajo|delta",
  "generado_en": "2026-11-04T10:00:00",
  "generado_por": "g360-ventas-db/1.0.0",
  "rango": {"desde": "2020-01-01", "hasta": "2026-11-03"},
  "sha256": "<checksum_del_historial.db>",
  "quick_check": {"ok": true, "filas": 2826817, "soles": 12345678.90},
  "dias": ["2026-11-01", "2026-11-02", ...],
  "day_checksums": {
    "2026-11-01": {"filas": 450, "soles": 12500.50, "checksum": "450:12500.50"}
  },
  "config": {
    "allowlist": [],
    "nota": "documentación, no se aplica al importar"
  },
  "espejo_completo": true,
  "sidecar": {
    "archivo": "estado_sustentor.db",
    "sha256": "<checksum>"
  }
}
```

Campos obligatorios: `version`, `sha256`, `day_checksums`, `espejo_completo`.
El importador los usa para:
- Verificar integridad (`sha256` vs archivo).
- Decidir superset vs merge (`day_checksums`).
- Validar que la semilla no filtra líneas (`espejo_completo`).

### 3.3 Quick check

Antes de cerrar el paquete, ejecutar:
```python
conn = sqlite3.connect("historial.db")
filas = conn.execute("SELECT COUNT(*) FROM ventas").fetchone()[0]
soles = conn.execute("SELECT COALESCE(SUM(soles),0) FROM ventas").fetchone()[0]
ok = verificar_contrato(conn)["ok"]
```
Escribir los resultados en `quick_check`. Si `ok=False`, no emitir.

---

## F4: ETL Supabase incremental por checksums

### 4.1 Estado de publicación

Tabla `etl_state` en el productor:

```sql
CREATE TABLE IF NOT EXISTS etl_state (
    key TEXT NOT NULL PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
-- key = "ultimo_dia_publicado", value = "2026-11-03"
-- key = "ultimo_mes_publicado", value = "2026-11"
```

### 4.2 Lógica de publicación

```
dias_a_publicar = [dia for dia in dias_recientes
                   if dia not in dias_ya_publicados]
for dia in dias_a_publicar:
    filas = SELECT * FROM ventas WHERE substr(fecha_orig,1,10) = dia
    publipg_upsert(filas)  # upsert por folio_unico
    registrar_en_etl_state(dia)
```

**No publicar** días cuyo `day_checksum` no cambió desde la última vez.

### 4.3 Proyección

La proyección en Supabase (tipos, RLS, catálogos normalizados) vive en el ETL,
no en el esquema canónico. El canónico sigue siendo ancho y denormalizado.

---

## F5: Herramienta offline "comparar dos DBs"

(el consumidor ya tiene `contraste_con_origen` en `db_network.py`).
El productor debe exponer un endpoint o comando que devuelva los `day_checksums`
completos para que el consumidor pueda comparar sin abrir la DB remota.

```bash
# Ejemplo de CLI
g360-ventas-db compare-checksums --db historial.db --output checksums.json
```

El JSON resultante tiene la forma:
```json
{"2026-11-01": {"filas": 450, "soles": 12500.50, "checksum": "450:12500.50"}, ...}
```

---

## Tests de aceptación

### En este repo (sustentor)

```bash
uv run pytest tests/test_fixture_doradas.py -v
uv run pytest tests/test_contrato_db.py -v
uv run pytest tests/test_cartucho.py -v
```

### En el repo Tauri (deben pasar las mismas fixtures)

El Tauri debe tener un test que:
1. Lea `tests/fixtures_doradas/fechas_crudas.json`.
2. Inserte las filas `input` en su DB.
3. Verifique que las filas结果 tienen `fecha_orig` en ISO.
4. Repita con `id_pedido_espacios.json` y `mes_ref_derivado.json`.

Si el Tauri no pasa estas fixtures, el consumidor detecta el drift en su CI.

---

## Compatibilidad

- El consumidor acepta `version >= 3 AND version < 5`.
- Un bump de `version` a 5 significa cambio de schema rompería; el consumidor
  levanta `ContratoDBError`.
- `normalizacion_version` puede bumpiar sin romper compatibilidad (es una
  regla de saneamiento, no de schema).

---

## Resumen de lo que el consumidor deja de hacer

| Ahora hace el consumidor | Lo delega al productor |
|---|---|
| Calcular `mes_ref` en el INSERT | Ya viene calculado |
| Normalizar fechas al copiar | Ya vienen ISO |
| Barrido de `id_pedido` en `init_db` | Ya viene normalizado |
| Crear índices al importar | Ya vienen en la DB |
| Recalcular `day_checksums` | Ya vienen en el paquete |
| Exportar cartucho desde la DB local | Lo emite el productor |

---

## Qué NO se delega

- `agg_cliente_mes` / `nc_asociadas` / `stats_cache` (dependen de la allowlist
  local).
- `day_state` (estado de cada día: provisional/cerrado).
- `oc_alias` (normalización de O/C por cliente).
- Allowlist (política del cliente).

Estos tres son locales y no deben viajar.
