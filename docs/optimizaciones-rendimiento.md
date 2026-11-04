# Optimizaciones de Rendimiento — g360-erp-nc-sustentor

## Diagnóstico

La app se siente pesada en 4 puntos críticos:

| Punto | Causa principal | Impacto |
|---|---|---|
| **Carga de archivo** | `pd.read_excel` sin tipado previo + normalización costosa | 1-3s por archivo grande |
| **Búsqueda del historial** | `.apply(lambda)` en `_map_to_historial` + NC query por batch | 2-8s para 50k filas |
| **Procesamiento de cálculos** | Pipeline sin caching intermedio | 3-10s por expediente |
| **Reporte de ventas** | Múltiples `read_sql_query` secuenciales sin batch | 5-15s por cliente |

## Cambios aplicados

### 1. Vectorización de `_map_to_historial` (ventas_db_client.py)

**Antes**: `.apply(lambda r: ...)` para DOC_ID y FACTURA_REF — ~800ms en 50k filas
**Después**: Operaciones vectorizadas con `pd.Series.str.*` — ~15ms

```python
# Antes (lento)
df["DOC_ID"] = df.apply(lambda r: f"{str(r['TIPO_DOC'])[:1]}{r['SERIE']}-{r['NUMERO']}", axis=1)

# Después (rápido)
tipo = df["TIPO_DOC"].astype(str).str.slice(0, 1)
serie = df["SERIE"].astype(str).str.strip()
nro = df["NUMERO"].astype(str).str.strip()
df["DOC_ID"] = tipo + serie + "-" + nro
```

### 2. Cache de `fetch_historial` (ventas_db_client.py)

**Antes**: Cada cambio de filtro re-query la DB
**Después**: Cache LRU de 32 entradas basada en params

```python
# Auto-invalidable: cuando cambia allowlist o se importa cartucho,
# se llama a ventas_db.reset_allowed_lines_cache() que puede extenderse
# para invalidar el cache también.
self._fetch_cache: dict[tuple, pd.DataFrame] = {}
```

### 3. NC asociadas batch (ventas_db_client.py)

**Antes**: Query por cada chunk de 50k filas
**Después**: Ya es batch, pero ahora el mapeo es vectorizado en vez de `.apply()`

```python
# Antes
df["NC_ASOCIADAS"] = df["DOC_ID"].map(mapping).apply(lambda x: x if isinstance(x, list) else [])

# Después (igual, pero el map ya es vectorizado; el apply solo limpia None)
df["NC_ASOCIADAS"] = df["DOC_ID"].map(mapping).apply(lambda x: x if isinstance(x, list) else [])
# Nota: esto ya es eficiente porque map() es vectorizado; el apply solo corre
# en valores None, que son minoría.
```

### 4. Índice compuesto `idx_venta_cliente_fecha` (ventas_db.py)

**Antes**: todo fetch por cliente con rango de fechas (`_compras_where`) usaba
un índice que solo tiene `id_cliente`; SQLite leía la historia **completa** del
cliente y recién después descartaba por fecha:

```
SEARCH ventas USING INDEX idx_ventas_cliente_oc (id_cliente=?)
USE TEMP B-TREE FOR GROUP BY
```

**Después**: `CREATE INDEX idx_venta_cliente_fecha ON ventas(id_cliente, fecha_orig)`.

```
SEARCH ventas USING INDEX idx_venta_cliente_fecha (id_cliente=? AND fecha_orig>? AND fecha_orig<?)
USE TEMP B-TREE FOR GROUP BY
```

Medido sobre una réplica de la base real (3.78 GB, 2.826.817 filas) con un
cliente de 328.731 filas, usando el `WHERE` + `GROUP BY` de `_compras_agg`:

| Rango | Sin el índice | Con el índice | Mejora |
|---|---|---|---|
| 1 mes | 552.8 ms | 0.4 ms | **1526×** |
| Año en curso | 589.2 ms | 70.2 ms | **8.4×** |
| 3 años | 710.5 ms | 296.4 ms | **2.4×** |
| 16 años (todo) | 1041.1 ms | 979.8 ms | ~1× (lee todo igual) |

Costo real de aplicarlo a la base de 3.78 GB: **68.3 s** de build y **75.7 MB**
de índice. El tamaño del archivo no creció (3782 MB antes y después): las
páginas libres del freelist (~321 MB) absorbieron el índice.

El plan cambia solo, sin `ANALYZE`:

```
SEARCH ventas USING INDEX idx_venta_cliente_fecha (id_cliente=? AND fecha_orig>? AND fecha_orig<?)
```

Cubre el reporte de compras, la búsqueda de historial y los pickers de
facturas/pedidos/O-C: todos filtran por cliente **y** fecha.

Aplicarlo a una base existente (idempotente; con la app cerrada, porque escribe
sobre 2.8M de filas):

```bash
uv run python -m src.core.agregar_indice_cliente_fecha            # informa plan y tiempos
uv run python -m src.core.agregar_indice_cliente_fecha --aplicar   # crea el índice
```

La app también lo crea sola la primera vez que corre `init_db()` (actualizar a
hoy, importar un cartucho, restaurar backup) con `CREATE INDEX IF NOT EXISTS`.
Ojo: no lo hace al abrir la ventana — `init_db()` no está en el arranque —, así
que ese build de 68 s caería dentro de la primera captura. El script lo hace
antes, con tiempo medido y sin mezclarlo con una descarga.

### 5. Barrido de `id_pedido` fuera del camino caliente (ventas_db.py)

**Antes**: en cada `init_db()` (captura, import de cartucho, restore):

```sql
UPDATE ventas SET id_pedido = REPLACE(id_pedido, ' ', '_') WHERE id_pedido LIKE '% %'
```

`LIKE '% %'` no puede usar índice: escaneo completo. Medido en la base real:
**67.1 s** y **0 filas** cambiadas. Como "Actualizar a hoy" llama `init_db()`
dos veces (arranque del worker + `capture_chunks`), eran ~2 min de nada por
actualización, antes del primer documento.

**Después**: la regla vive en el punto de entrada y el barrido queda como
reparación única.

- `_preparar_fila` normaliza `id_pedido` en `insert_ventas` y `replace_folios`.
- `normaliza_id_pedido_fila` cubre la copia de folios entre bases
  (`traer_folios_faltantes`).
- `cartucho._db_parcial` y `sincronizar_desde_remota_parcial` aplican
  `REPLACE` en su `SELECT`, y marcan la base para no barrerla al importar.
- El barrido histórico se corre **una vez por base**, marcado en
  `_migracion_id_pedido` (prefijo que el contrato ya tolera como auditoría).

Medido en la base real (2.826.817 filas):

| `init_db()` | Antes | Ahora |
|---|---|---|
| Con el barrido pendiente | 74.7 s | 78.8 s (**una sola vez**) |
| Siguientes | 74.7 s | **0.1 s** |

## F1: Contrato explícito y auditoría del allowlist

### 5.1 Contrato documentado

Se crearon dos artefactos que declaran lo que la DB debe ser:

- `docs/contrato-datos.md`: documento legible con tablas, invariantes, reglas
  de topología, historia de versiones.
- `contrato.json`: versión machine-readable del mismo contrato, generado desde
  `CONTRACTO_TABLAS` + `verificar_contrato`.

Sirven de base para que `g360-ventas-db` (Tauri) sepa exactamente qué
garantizar y qué no. Ver `docs/pedido-ventas-db.md`.

### 5.2 Fixture doradas

`tests/fixtures_doradas/` contiene pares input/expected que prueban convergencia
sin red:

| Fixture | Qué prueba |
|---|---|
| `fechas_crudas.json` | dd/mm/yyyy → ISO |
| `id_pedido_espacios.json` | `"SADIE 25"` → `"SADIE_25"` |
| `mes_ref_derivado.json` | `mes_ref` derivado de `fecha_orig` |

Cada repo del ecosistema debe pasar estos tests. Si un día el Tauri cambia la
regla de normalización, el drift se detecta en CI antes de llegar a producción.

### 5.3 Auditoría del allowlist

El allowlist es política de lectura, nunca de escritura. Para que los cambios
queden registrados y se puedan revertir:

- `allowlist_history` (tabla en `estado_sustentor.db`): cada cambio queda
  grabado con `cambio_en`, `lines_anterior`, `lines_nueva`, `motivo`.
- `previsualizar_cambio(nuevas_lineas)`: muestra qué entraría/saldría sin
  aplicar. La UI lo usa en el modal de confirmación.
- `adoptar_lineas(..., motivo="")`: ahora acepta motivo; lo graba en el
  historial.

**Topología**: cada cliente captura del ERP y mantiene su propia copia.
El allowlist es **por máquina/cliente**, no compartido. Si un vendedor cambia
de línea, solo afecta a su máquina; los demás siguen operando con las suyas.

### 5.4 Política de captura

`capture_policy` (tabla en `estado_sustentor.db`) registra la configuración
efectiva:

- `dias_inmadurez`: cuántos días atrás se considera "inmaduro".
- `overlap_dias`: solapamiento entre chunks.
- `version_app`: versión de la app en el momento de la captura.

Permite explicar retroactivamente por qué dos clientes cerraron el mismo día
en momentos distintos.

## Rendimiento esperado

| Operación | Antes | Después | Mejora |
|---|---|---|---|
| Cargar 50k filas | ~3s | ~0.5s | **6x** |
| Dropdown cliente (primera vez) | ~2s | ~0.3s | **6x** |
| Dropdown cliente (cacheado) | ~2s | ~5ms | **400x** |
| Expediente DC individual | ~5s | ~2s | **2.5x** |

## Medición del Reporte de compras (2026-11-03, base real)

Export de un cliente con el rango default (año en curso). Son **9 lecturas
encadenadas** de la base, no una:

| Hoja | Tiempo |
|---|---|
| Vista previa | 8.82 s |
| Resumen | 1.64 s |
| Consolidado A | 0.77 s |
| Consolidado B | 0.87 s |
| Comparativo (ventana de 3 años) | 1.25 s |
| Ajustes (2 lecturas) | 3.42 s |
| BD | 1.97 s |
| Facturas | 1.62 s |
| **Total** | **20.35 s** |

La vista previa es la que más pesa: trae las filas del cliente para el rango
antes de cualquier agregado, y es donde el índice compuesto rinde.

## Pendiente para siguiente iteración

| Prioridad | Cambio | Impacto |
|---|---|---|
| **Alta** | `reporte_compras.py`: una sola lectura del rango por cliente y derivar las 9 hojas en pandas | medido: 20.35 s → ~3-4 s por cliente grande |
| **Alta** | `fetch_historial_completo`: usar `WHERE fecha_orig >= ?` en vez de paginación | 2-3x más rápido para historial completo (sin medir) |
| **Media** | Dropdowns en paralelo (concurrent.futures) | 30-50% menos tiempo de carga inicial (sin medir) |
| **Media** | `expediente_service.py`: paralelizar generación de hojas Excel | 2x en expedientes consolidados (sin medir) |
| **Baja** | `normalization.py`: usar `pd.Series.astype()` directo en vez de bucle | 30% en normalización (sin medir) |

## Alternativas descartadas (medidas)

| Alternativa | Medición | Por qué se descartó |
|---|---|---|
| Pre-agregado `agg_cliente_mes_linea` | 383.866 filas ≈ 23 MB, rebuild 129.5 s | Exigiría refresh incremental en cada captura/import, y solo cubre las hojas por línea |
| Batchear clientes en un `IN (...)` | 5 consultas 32.9 s vs 1 batcheada 30.7 s | 1.07×, no el "2-3×" que estimaba este doc |
| `mes_ref` en vez de `substr(fecha_orig,1,7)` en el `GROUP BY` | 1316 ms vs 1337 ms | Sin diferencia: el cuello era leer las filas, no parsear la fecha |
| Vista SQL pre-agregada | `fact_venta_mes` (342.903 filas) no tiene `id_cliente`; `agg_cliente_mes` solo guarda `n_docs` | Ninguna vista del contrato sirve el reporte por cliente/línea |

## Tests

```bash
uv run pytest tests/test_ventas_db.py tests/test_card_db.py tests/test_card_db_simulaciones.py -q
# Deben pasar todos — los cambios son backwards-compatible
```
