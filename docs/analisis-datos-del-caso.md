# Análisis: Sección "Datos del caso"

## Flujo actual

### 1. Rango de fechas
- Dos campos de texto (`busq_fd`, `busq_fh`) con date picker integrado
- Por defecto: últimos 30 días desde hoy
- Se persiste entre re-renderizados (cambio de caso no lo resetea)
- `_rango_str()` devuelve `(fd_str, fh_str)` en formato `YYYY-MM-DD`

### 2. Selección de cliente
- **Picker modal** con búsqueda en tiempo real
- Consulta: `fetch_clientes(vendedor_id, fecha_desde, fecha_hasta, search, limit, offset)`
- **Fast-path**: si `agg_cliente_mes` está poblado, usa esa tabla resumen (~27K filas) en vez de escanear 1.5M → rangos largos caen de ~3.3s a <20ms
- Muestra top clientes por documentos (DESC), con anclados (favoritos) primero
- Soporta paginación (`offset`) para "cargar más"
- `search`: LIKE case-insensitive por id/nombre/doc

### 3. Chips de selección
Cada selección genera un chip con botón de eliminar:

| Chip | Atributo | Formato label | Query usada |
|---|---|---|---|
| Cliente | `_sel_clientes` | "NOMBRE (ID)" | — |
| Pedido | `_sel_pedidos` | "Pedido · ID" | `fetch_pedidos_cliente(cid, fd, fh)` |
| O/C | `_sel_ordenes` | "O/C · ID" | `fetch_ordenes_cliente(cid, fd, fh)` |
| Factura | `_sel_facturas` | "F204-67375" | `fetch_facturas_cliente(cid, fd, fh)` |

### 4. Botones documentales
Al seleccionar cliente, se muestran botones para abrir pickers de:
- **Pedidos** (si hay >0)
- **O/C** (si hay >0)
- **Facturas** (si hay >0)

Cada uno abre un modal con lista checkbox + búsqueda interna.

### 5. Ejecución de búsqueda
Botón "Buscar" → `_busq_executar()`:

```python
# Agrupa filtros por cliente
ocl_por_cli = {cid: [ocs]}
ped_por_cli = {cid: [peds]}
fac_por_cli = {cid: {refs}}

# Para cada cliente con filtros:
if ocl o ped:
    fetch_historial(id_cliente=cid, ordenes=oc_list, id_pedidos=ped_list, fecha_desde=fd, fecha_hasta=fh)
    # Luego filtra por DOC_ID si hay facturas
elif fac:
    fetch_historial(id_cliente=cid, serie_doc=serie, nro_doc=nro)
else:
    fetch_historial(id_cliente=cid, fecha_desde=fd, fecha_hasta=fh)

# Concatena todos los DFs
df = pd.concat(dfs, ignore_index=True)

# Dedup por FOLIO_UNICO + CODIGO
```

### 6. Aplicar fragmento
Botón "USAR COMO HISTORIAL" → `_aplicar_fragmento()`:
- Guarda `df` en `self.df_historial`
- Actualiza dropdowns (clientes, vendedores, facturas)
- Muestra snackbar con conteo de filas

---

## Observaciones

### ✅ Correcto
1. **Cached de clientes**: Usa `agg_cliente_mes` cuando disponible (fast-path ~20ms vs ~3.3s)
2. **Dedup por folio**: Evita duplicados al concatenar resultados
3. **Persistencia de rango**: No se resetea al cambiar de caso
4. **Chips eliminables**: Cada chip tiene `on_delete` funcional
5. **Thread-safe**: La búsqueda corre en `threading.Thread(daemon=True)`

### ⚠️ Mejorable

| # | Problema | Impacto | Recomendación |
|---|---|---|---|
| 1 | **Sin filtro por SKU** | No se puede buscar por artículo específico | Agregar chip de SKU como los otros (pedido, OC, factura) |
| 2 | **Último cliente gana** | `_sel_clientes[-1][0]` en pickers de doc | Si hay múltiples clientes, los pickers usan solo el último seleccionado |
| 3 | **NC asociadas no se filtra** | La query de historial trae NC sin filtrar por DOC_ID si hay facturas seleccionadas | El filtro por facturas se aplica post-query con `.isin(refs)` — correcto pero ineficiente |
| 4 | **Preview solo 5 filas** | `nrows=5` en `_cargar_preview_insumo` | Aumentar a 10-20 para mejor visibilidad |
| 5 | **Sin indicador de carga** | No hay spinner mientras busca | Agregar `show_loading` al iniciar `_busq_executar` |

### 🔴 Bug potencial

**Línea 4993-4997**: El filtro de facturas tiene un edge case:

```python
for fid in fac_por_cli[cli]:
    parts = fid.split("-", 2)
    if len(parts) >= 3:
        refs.add(f"{parts[0][:1]}{parts[1]}-{parts[2]}")
```

Si `fid` viene como `"F01-204-67375"`:
- `parts[0][:1]` = `"F"`
- `parts[1]` = `"204"`
- Resultado: `"F204-67375"` → correcto

Pero si viene como `"F204-67375"` (sin ceros a la izquierda en serie):
- `parts[0][:1]` = `"F"`
- `parts[1]` = `"204"`
- Resultado: `"F204-67375"` → también correcto

El problema es cuando `fid` ya tiene el formato correcto y `parts[0]` es algo como `"F01"`:
- `parts[0][:1]` = `"F"` → se pierde el `"01"`!

Esto hace que el filtro de facturas pueda ser **inexacto** en algunos casos.

---

## Tests existentes

`tests/test_datos_del_caso_chips.py` (7 tests):
- ✅ Chips ocultos al construir
- ✅ Chips se pintan con datos
- ✅ Botones documentales condicionales
- ✅ Geometría del card
- ✅ Picker sin page no crashea
- ✅ Rango de fechas persiste
- ✅ Insumos sobreviven re-render

---

## Resumen ejecutivo

El flujo es **funcional y bien diseñado** con buen uso de caching. Los principales gap son:

1. **Falta filtro por SKU** — el usuario no puede restringir a un artículo específico
2. **Bug potencial en filtro de facturas** — el slicing `parts[0][:1]` puede truncar el tipo de documento
3. **Multi-cliente**: los pickers de docs usan solo el último cliente seleccionado

Para uso producción actual, el flujo funciona bien con **un solo cliente**. Con múltiples clientes, el comportamiento de los pickers de documentos puede no ser el esperado.
