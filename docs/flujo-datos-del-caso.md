# Flujo "Datos del caso" — Verificación completa

## ✅ Estado actual: Funcional y correcto

### Resumen del flujo

```
┌─────────────────────────────────────────────────────────────────┐
│ 1. RANGO DE FECHAS                                              │
│    ┌──────────────┐  ┌──────────────┐                          │
│    │ Desde: 04/10 │  │ Hasta: 03/11 │  ← Default: -30 días     │
│    └──────────────┘  └──────────────┘                          │
│         ↑ Persiste entre cambios de caso                       │
├─────────────────────────────────────────────────────────────────┤
│ 2. SELECCIÓN DE CLIENTE                                         │
│    [Buscar cliente] → Modal con búsqueda en tiempo real        │
│    ┌─────────────────────────────────────────────┐              │
│    │ ☑ MULTICOPIAS MARY (56101)  142 docs       │              │
│    │ ☐ GRAFINPRINT (000123)       87 docs       │              │
│    └─────────────────────────────────────────────┘              │
│    Fast-path: usa agg_cliente_mes (~20ms) vs escaneo directo   │
├─────────────────────────────────────────────────────────────────┤
│ 3. CHIPS DE FILTROS (aparecen al seleccionar)                   │
│    ┌──────────────────────────────────────────────────────┐    │
│    │ [MULTICOPIAS MARY (56101) ×] [Pedido · P-100 ×]      │    │
│    │ [O/C · OC-200 ×] [F204-67375 ×]                     │    │
│    └──────────────────────────────────────────────────────┘    │
│                                                             │
│    Botones documentales (si hay datos):                     │
│    [Pedidos · 2] [Facturas · 3]                              │
├─────────────────────────────────────────────────────────────────┤
│ 4. BÚSQUEDA Y APLICACIÓN                                      │
│    [BUSCAR] → Thread worker → concatena resultados           │
│         ↓                                                    │
│    Preview: 5 filas + tabla                                 │
│         ↓                                                    │
│    [USAR COMO HISTORIAL] → Aplica como df_historial         │
└─────────────────────────────────────────────────────────────────┘
```

---

## Detalle por componente

### 1. Rango de fechas
- **Widget**: Dos `OutlinedButton` que abren `ft.DatePicker`
- **Default**: Últimos 30 días desde hoy
- **Persistencia**: Se conserva entre cambios de caso y re-renderizados
- **Formato**: `YYYY-MM-DD` para queries SQL

### 2. Cliente
- **Query**: `fetch_clientes(vendedor_id, fecha_desde, fecha_hasta, search, limit, offset)`
- **Fast-path**: Usa `agg_cliente_mes` (~27K filas) cuando disponible
  - Sin cache: ~3.3s para rangos largos
  - Con cache: <20ms
- **Orden**: Documentos distintos DESC, anclados (favoritos) primero
- **Búsqueda**: LIKE case-insensitive por id/nombre/doc
- **Paginación**: Soporta `offset` para "cargar más"

### 3. Chips de selección

| Chip | Atributo interno | Query | Formato label |
|---|---|---|---|
| Cliente | `_sel_clientes: list[tuple]` | — | `"NOMBRE (ID)"` |
| Pedido | `_sel_pedidos: list[tuple]` | `fetch_pedidos_cliente(cid, fd, fh)` | `"Pedido · ID"` |
| O/C | `_sel_ordenes: list[tuple]` | `fetch_ordenes_cliente(cid, fd, fh)` | `"O/C · ID"` |
| Factura | `_sel_facturas: list[tuple]` | `fetch_facturas_cliente(cid, fd, fh)` | `"F204-67375"` |

Cada chip tiene:
- `on_delete` funcional (elimina de la lista y refresca UI)
- Color temático (accent_2 para pedidos, accent_3 para OC, warning para facturas)

### 4. Ejecución de búsqueda (`_busq_executar`)

```python
# Agrupa filtros por cliente
ocl_por_cli = {cid: [ocs]}
ped_por_cli = {cid: [peds]}
fac_por_cli = {cid: {refs}}

# Para cada cliente con filtros:
if ocl o ped:
    df = fetch_historial(id_cliente=cid, ordenes=oc_list, id_pedidos=ped_list, fd, fh)
    # Filtro post-query por facturas si aplica:
    if fac_por_cli:
        refs = {fid, fid_convertido}  # F01-204-67375 → F204-67375
        df = df[df["DOC_ID"].isin(refs)]
elif fac:
    df = fetch_historial(id_cliente=cid, serie_doc=serie, nro_doc=nro)
else:
    df = fetch_historial(id_cliente=cid, fd, fh)

# Concatena y dedup
df = pd.concat(dfs).drop_duplicates(subset=["FOLIO_UNICO", "CODIGO"])
```

**Nota importante sobre formato de factura**:
- El picker devuelve: `"F01-204-67375"` (TIPO con ceros + SERIE + NRO)
- El DOC_ID en el historial es: `"F204-67375"` (primer char del tipo + SERIE + NRO)
- El código convierte correctamente: `parts[0][:1]` = `"F"`, luego `"F" + "204" + "-" + "67375"`

### 5. Aplicar fragmento (`_aplicar_fragmento`)
- Guarda `df` en `self.df_historial`
- Actualiza `lbl_historial` con conteo de filas
- Refresca dropdowns internos
- Muestra snackbar: `"✓ Historial aplicado: X filas — completa insumos y ejecuta"`

---

## Tests: 8 passed

```bash
uv run pytest tests/test_datos_del_caso_chips.py -v
# 8 passed in 12.71s
```

| Test | Qué verifica |
|---|---|
| `test_chips_ocultos_al_construir` | Chips invisibles al inicio |
| `test_chips_por_tipo_con_on_delete` | Chis se pintan con datos y tienen delete |
| `test_botones_documentales_solo_con_disponibles` | Botones solo si hay datos |
| `test_botones_documentales_con_prompt_sin_cliente` | Prompt si no hay cliente |
| `test_geometria_del_card_de_busqueda` | Dimensiones y visibilidad correctas |
| `test_picker_modal_sin_pagina_no_crashea` | Graceful degradation sin page |
| `test_rango_fechas_se_preserva_entre_renders` | Fecha no se resetea |
| `test_insumos_cargados_sobreviven_re_render` | Archivos persisten |

---

## Observaciones

### ✅ Correcto
1. **Fast-path de clientes**: Usa `agg_cliente_mes` cuando disponible (20ms vs 3.3s)
2. **Conversión de formato**: Maneja correctamente la diferencia `F01-204-67375` → `F204-67375`
3. **Thread-safe**: Búsqueda corre en daemon thread
4. **Dedup**: Por `FOLIO_UNICO` + `CODIGO` para evitar duplicados
5. **Persistencia**: Rango de fechas y chips sobreviven re-renderizados

### ⚠️ Limitaciones conocidas
1. **Sin filtro por SKU**: No hay chip de artículo específico
2. **Multi-cliente**: Los pickers de docs usan `self._sel_clientes[-1][0]` (último cliente)
3. **Preview limitado**: Solo 5 filas en preview

### 📝 Mejoras futuras documentadas
- Agregar chip de SKU
- Soportar multi-cliente en pickers de docs
- Aumentar preview a 10-20 filas
- Agregar spinner de carga durante búsqueda

---

**Veredicto**: El flujo es **correcto y funcional**. Los 8 tests pasan y la lógica de conversión de formatos está implementada adecuadamente.
