# Contrato de datos — historial.db

## Principio

El archivo `historial.db` es el único depósito de verdad del sustentor.
Ninguna tabla derivada, ningún estado local, ningún sidecar anula su autoridad.
Cuando un valor cambia, la DB se reconstruye — nunca al revés.

Este documento declara qué es cada tabla, para qué sirve, y qué **no** es.
Si alguna convención no está aquí, está prohibida.

---

## Topología

```
ERP intranet ──▶ g360-ventas-db (Tauri) ──▶ historial.db (semilla)
                                        │
                                        ├──▶ Supabase (proyección, solo lectura)
                                        │   ETL por checksums, unidireccional.
                                        │
                                        └──▶ g360-erp-nc-sustentor (clientes)
                                            captura local incremental
                                            allowlist por línea, por máquina
```

Reglas de topología:

- **Una fuente**: el ERP. El Tauri lo descarga; los clientes lo capturan en paralelo.
- **Sin replicación entre clientes**: cada máquina mantiene su propia copia de
  `ventas` y su propia política (`allowlist`, `day_state`). No hay lock ni
  coordinación entre clientes.
- **Convergencia por determinismo**: si dos clientes capturan el mismo día del
  mismo ERP, deben producir las mismas filas. Ese contrato se prueba con
  *fixtures doradas*, no con red.
- **Semilla = espejo completo**: el Tauri emite toda la tabla `ventas` sin
  filtro de líneas. El allowlist es política de lectura, nunca de escritura.

---

## Versión del contrato

| Campo | Valor actual | Qué significa |
|---|---|---|
| `user_version` | 3 | Cada bump requiere migración explícita del consumidor |
| `normalizacion_version` | 1 | Cada bump reaplica las reglas de saneamiento sin romper DBs existentes |

Regla: un cliente acepta un rango `>=v_actual <v_actual+2`. Si el productor
bumpia a una versión mayor, la app levanta `ContratoDBError` y bloquea hasta
que el consumidor se actualice. Esto evita que una DB de forma desconocida
guíe reportes silenciosamente.

---

## Tablas del contrato (`ventas`)

### Estructura

Columnas en orden (ver `CONTRACTO_TABLAS["ventas"]` en `ventas_db.py`):

| # | Columna | Tipo implícito | Nota |
|---|---|---|---|
| 1 | `id` | INTEGER PK AUTOINCREMENT | Key interna; no viaja en el cartucho |
| 2 | `id_articulo` | TEXT NOT NULL | SKU del ERP |
| 3 | `original_sku` | TEXT | SKU tal como llega |
| 4 | `nom_articulo` | TEXT | Descripción |
| 5 | `id_linea` | TEXT NOT NULL | sufijo de sucursal (ej. `0101`) → allowlist compara esto |
| 6 | `nom_linea` | TEXT | "GASEOSAS", etc. |
| 7 | `id_grupo` / `nom_grupo` | TEXT | Agrupación comercial |
| 8 | `id_tipo` / `nom_tipo` | TEXT | Subtipo |
| 9 | `id_familia` / `nom_familia` | TEXT | Familia |
| 10 | `id_cliente` | TEXT NOT NULL | RUC/CE del cliente |
| 11 | `doc_cliente` | TEXT | Documento de identidad |
| 12 | `nom_cliente` | TEXT | Razón social |
| 13 | `tpo_doc` | TEXT NOT NULL | F012, NCR, NDB, etc. |
| 14 | `serie_doc` | TEXT | Serie del comprobante |
| 15 | `nro_doc` | TEXT | Número |
| 16 | `referencia` | TEXT | Referencia cruzada |
| 17 | `moneda` | TEXT | "Soles" / "Dólares" |
| 18 | `cantidad` | REAL NOT NULL | Unidades |
| 19 | `soles` | REAL NOT NULL | Monto en soles |
| 20 | `dolares` | REAL | Monto en dólares (NULL si no aplica) |
| 21 | `precio_unitario` | REAL | Precio unitario |
| 22 | `cantidad_fae` | REAL | FAE (crédito documentado) |
| 23 | `anho` | INTEGER NOT NULL | Derivado de `fecha_orig` |
| 24 | `mes` | INTEGER NOT NULL | Derivado de `fecha_orig` |
| 25 | `fecha_orig` | TEXT NOT NULL ISO | Fecha del documento — invariante crítica |
| 26 | `fecha_ref` | TEXT ISO | Fecha de referencia (nullable) |
| 27 | `fecha_venc` | TEXT ISO | Fecha de vencimiento (nullable) |
| 28 | `cod_sucursal` | TEXT | Código de sucursal |
| 29 | `nom_sucursal` | TEXT | Nombre de sucursal |
| 30 | `departamento` | TEXT | Geografía |
| 31 | `provincia` | TEXT | Geografía |
| 32 | `distrito` | TEXT | Geografía |
| 33 | `id_vendedor` | TEXT | ID del vendedor |
| 34 | `nom_vendedor` | TEXT | Nombre del vendedor |
| 35 | `id_pedido` | TEXT | Pedido normalizado (espacios → `_`) |
| 36 | `ord_compra` | TEXT | Orden de compra |
| 37 | `file_source` | TEXT | Origen del registro |
| 38 | `mes_ref` | TEXT NOT NULL | `YYYY-MM` canónico |
| 39 | `capturado_en` | TEXT DEFAULT | Timestamp de inserción local |
| 40 | `tipo_operacion` | TEXT DEFAULT | "venta" u otro |
| 41 | `factura_ref_serie` / `factura_ref_nro` | TEXT | Fac. referenciada |
| 42 | `folio_unico` | TEXT | Hash del documento |
| 43–50 | Extra (fat DB) | — | `id_ubigeo`, `canal_distribucion`, `nom_condicion_pago`, `estado_linea`, `division`, `fec_cargo`, `id_guia` |

### Invariantes

| Invariante | Cómo se garantiza | Qué pasa si se rompe |
|---|---|---|
| Fechas en ISO (`YYYY-MM-DD`) | `_normaliza_fechas_venta()` en el punto de entrada; `LIKE '%/%'` detecta regresiones | `fecha_orig` fuera de ISO → `BETWEEN` falla; los meses se separan |
| `id_pedido` sin espacios | `_preparar_fila()` → `"_" .join(str(v).split())` | Mismo pedido aparece dos veces en pickers |
| `mes_ref` = `substr(fecha_orig,1,7)` | Cálculo en `insert_ventas` + rebuild al importar | Grupos de meses inconsistentes |
| Espejo completo (sin filtro de líneas) | `insert_ventas` escribe TODO; el allowlist filtra en lectura | Semilla inútil para nuevas divisiones |
| Idempotencia por día | DELETE-then-INSERT por `substr(fecha_orig,1,10)` en cada sync | Duplicados acumulados |

### Índices

`CREATE_INDEXES` en `ventas_db.py` es la lista completa. Los críticos:

- `idx_venta_cliente_fecha` — `(id_cliente, fecha_orig)`: todo fetch por cliente
  lo usa. Medido: 1526× más rápido vs escaneo.
- `idx_venta_mes_checksum` — covering index para agregados mensuales
- `idx_venta_linea_nom` — covering index para `distinct_lineas()`
- `idx_ventas_folio_articulo` — lookup de documentos
- `idx_venta_oc` — filtrado por orden de compra

Un índice nuevo no requiere bump de versión; uno que se dropea sí, porque
destruye el rendimiento esperado.

---

## Tablas locales toleradas

| Tabla | Dueño | Vida |
|---|---|---|
| `agg_cliente_mes` | sustentor | Caché derivado del allowlist; se reconstruye al cambiarlo |
| `nc_asociadas` | sustentor | Caché de relaciones NC/factura |
| `stats_cache` | sustentor | Métricas de dashboard |
| `day_checksums` | sustentor | Checksum por día → merge/superset en import |
| `oc_archivos` | sustentor | Historial de archivos procesados |

Cualquier otra tabla extra rompe el contrato (`tablas_extra_no_toleradas`).
Excepción: tablas con prefijo `_migracion_` (auditoría de migraciones).

---

## Estado del cliente (`estado_sustentor.db`)

Vive fuera de `historial.db` porque es **local**, no compartido:

| Tabla | Propósito |
|---|---|
| `day_state` | Estado de cada día (`provisional` / `cerrado`) |
| `oc_alias` | Normalización de órdenes de compra `(id_cliente, oc_raw → oc_norm)` |

El `day_state` se reconstruye desde `day_checksums` al importar un cartucho
(`reconstruir_day_state`). El `oc_alias` viaja en el sidecar del cartucho.

---

## Semilla y cartucho

### Semilla

Emite el Tauri. Es una DB básica con el schema completo pero **sin índices ni derivados**:

```
historial.db      ← ventas + tablas vacías (schema del app)
CARTUCHO.json     ← manifiesto: versión, checksums, rango, sha256
config_sanitizado.json ← allowlist (vacía en semilla)
```

La semilla no lleva `agg_*`, `stats_cache`, `day_checksums`, ni `oc_alias`.
El receptor reconstruye todo en `init_db()`.

Invariante de la semilla: **espejo completo del segmento ERP**. Sin filtro de
líneas, sin allowlist, sin división. Si el Tauri filtra, la semilla ya no sirve
para todas las divisiones.

### Cartucho de trabajo

Lo emite un cliente y lo importa otro (o el mismo cliente en otra máquina).
Contiene:

```
historial.db          ← ventas + derivados (agg, stats, checksums)
estado_sustentor.db   ← day_state + oc_alias
config_sanitizado.json ← allowlist + configuración segura
CARTUCHO.json         ← manifiesto completo
```

Modos de import:
- `reemplazar` — `backup()` previo → copia total → `init_db()` → rebuild de derivados.
- `merge` (incremental) — por rango `desde`/`hasta` → DELETE-then-INSERT de días → merge de sidecar.

El manifiesto es la autoridad para decidir superset vs merge: `day_checksums`
del cartucho vs los días presentes localmente.

---

## Reglas de normalización (punto de entrada)

Cada regla se aplica en `_preparar_fila()` / `normaliza_fechas_fila()` /
`normaliza_id_pedido_fila()`. Nunca en el SELECT de reportes.

| Regla | Ubicación | Ejemplo |
|---|---|---|
| Fechas ISO | `_normaliza_fechas_venta()` | `15/01/2024` → `2024-01-15` |
| `id_pedido` sin espacios | `_preparar_fila()` | `"SADIE 25"` → `"SADIE_25"` |
| `mes_ref` canónico | `_preparar_fila()` | `"2024-01-15..."` → `"2024-01"` |
| `fec_cargo` ISO | `normaliza_fechas_fila()` | `"04/11/2026"` → `"2026-11-04"` |

**Migraciones históricas** (`_migracion_*`): se corren UNA vez por DB, quedan
marcadas y nunca se repiten. El patrón evita que cada `init_db()` pague un
barrido de 2.8M filas.

---

## Allowlist

- **Qué es**: lista de líneas de producto (`id_linea`) que entran al sustento.
- **Dónde vive**: `config.json` del cliente (`allowed_lines`); se guarda con
  confirmación explícita en UI.
- **Qué NO es**: no filtra la escritura. `ventas` es espejo completo siempre.
- **Materialización**: `agg_cliente_mes` (caché que se reconstruye al cambiar).
- **Cambio**: debe registrarse en `allowlist_historial` (fecha, líneas antes,
  líneas después, motivo). La reversión es otro rebuild.
- **Preview**: antes de aplicar, mostrar qué documentos entran/salen para que
  el cambio sea visible.

---

## Fixture doradas (convergencia)

Para garantizar que dos clientes producen las mismas filas al capturar el
mismo día del ERP, cada repo mantiene un set de fixtures doradas:

```python
# Input: filas tal como salen del ERP (con dd/mm/yyyy y espacios en id_pedido)
INPUT = [
    {
        "tpo_doc": "F012", "serie_doc": "012", "nro_doc": "123",
        "id_articulo": "02211", "id_linea": "0101",
        "fecha_orig": "15/01/2024",  # crudo del ERP
        "id_pedido": "SADIE 25",      # con espacios
        "fec_cargo": "14/01/2024",    # dd/mm/yyyy
        ...
    },
]

# Output esperado: filas normalizadas (ISO, id_pedido limpio)
EXPECTED = [
    {
        "fecha_orig": "2024-01-15",
        "id_pedido": "SADIE_25",
        "fec_cargo": "2024-01-14",
        "mes_ref": "2024-01",
        ...
    },
]
```

Cada repo (sustentor + Tauri) debe pasar estos tests. Si un cambio rompe la
convergencia, el test falla en ambos repos al mismo tiempo — el drift se
detecta antes de llegar a producción.

Ubicación: `tests/fixtures_doradas/` con serialización JSON, y tests en
`tests/test_fixture_doradas.py`.

---

## Manifiesto (CARTUCHO.json)

Campos que viajan en cada export/import:

```json
{
  "version": 3,
  "normalizacion_version": 1,
  "tipo": "semilla|trabajo",
  "generado_en": "2026-11-04T10:00:00",
  "generado_por": "g360-ventas-db/1.0.0",
  "rango": {"desde": "2020-01-01", "hasta": "2026-11-03"},
  "sha256": "abc...",
  "quick_check": {"ok": true},
  "dias": ["2026-11-01", "2026-11-02", ...],
  "day_checksums": {
    "2026-11-01": {"filas": 450, "soles": 12500.50, "checksum": "450:12500.50"}
  },
  "config": {"allowlist": ["0101", "0102"], "nota": "documentación"},
  "espejo_completo": true,
  "sidecar": {"archivo": "estado_sustentor.db", "sha256": "def..."}
}
```

Reglas del manifiesto:
- `sha256` del artefacto es la única prueba de integridad en transporte (USB,
  share puntual). Un cartucho truncado falla `quick_check`.
- `espejo_completo: true` es invariante de la semilla: el Tauri nunca filtra.
- `day_checksums` es la fuente de verdad para merge vs superset en el import.

---

## Supabase

- Canal unidireccional: Tauri → Supabase. Los consumidores son solo lectura.
- ETL por checksums: solo se publican días cuyo `day_checksum` cambió.
- La proyección (tipos, RLS, catálogos normalizados) vive en el ETL, no en el
  esquema canónico. El canónico permanece ancho y denormalizado.

---

## Historia de versiones

| v | Cambio | Migración necesaria |
|---|---|---|
| 1 | Schema inicial | — |
| 2 | Se agrega `fec_cargo`, `id_guia`, `division` (fat DB) | Migración de normalización de fechas |
| 3 | Índices explícitos en contrato; `_migracion_*` tolerados; normalización `id_pedido` | Barrido único marcado en `_migracion_id_pedido` |

---

## Documento vivo

Este archivo se genera desde el código. Para regenerarlo:

```bash
python scripts/generar_contrato.py docs/contrato-datos.md
```

Cualquier divergencia entre el código y este documento es un bug. Si querés
cambiar una regla, primero cambiá el código, después regenerá el docs, después
commiteá ambos juntos.
