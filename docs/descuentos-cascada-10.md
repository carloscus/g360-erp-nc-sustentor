# Descuentos en Cascada — 10 Columnas

## Cambio realizado

Se ampliaron las plantillas de **Lista de Precios** (DC) y **Lista de Precios y Cantidades** (VRS) de 8 a **10 columnas de descuento** (`DESC01` … `DESC10`).

## Archivos modificados

| Archivo | Cambio |
|---|---|
| `src/render/templates.py` | Agregadas `DESC09`, `DESC10` a `_COLUMN_FORMATS`, `lista_precios.columnas`, `lista_precios_cantidad.columnas`, ejemplos y anchos de celdas |
| `src/render/excel_renderer.py` | Agregadas `DESC09`, `DESC10` a la documentación VRS (`diferencia_stock`) |
| `assets/templates/Lista_de_Precios.xlsx` | Regenerado con 10 columnas DESC |
| `assets/templates/Lista_de_Precios_y_Cantidades.xlsx` | Regenerado con 10 columnas DESC |

## Cómo funciona la cascada

La fórmula en el Excel de expediente es dinámica:

```
PRECIO_NETO = ROUND(PRECIO_BASE × (1-DESC01) × (1-DESC02) × … × (1-DESC10), 5)
```

Solo se aplican los descuentos que tienen valor ≠ 0. Las columnas vacías o con 0 son ignoradas automáticamente.

## Backend (automático, sin cambios)

El motor ya usa detección por patrón regex `^DESC\d+$`, por lo que:

- **Normalización** (`normalization.py`): detecta y normaliza cualquier `DESC01`…`DESC99`
- **Cálculo de precio neto** (`aplicar_cadena_descuentos`): itera sobre todas las columnas DESC encontradas
- **Renderizado Excel** (`excel_render_calculo.py`): construye la fórmula dinámicamente según las columnas presentes en el DataFrame

## Tipos de reconocimiento afectados

| Tipo | Clave | Efecto |
|---|---|---|
| **Diferencia de Precio** (DC) | `lista_precios` | Precio base × cascada de hasta 10 descuentos |
| **Diferencia de Stock** (VRS) | `lista_precios_cantidad` | Igual + cantidad a sustentar |

## Uso

1. Descargar plantilla desde la app (botón "Plantillas" → "Lista de Precios" o "Lista de Precios y Cantidades")
2. Completar columnas DESC01 a DESC10 con fracciones (0.05 = 5%)
3. Cargar el archivo como insumo `lista_precios` en el reconocimiento
4. El motor calcula `PRECIO_NETO` en cascada automáticamente

## Ejemplo

| SKU | PRECIO_BASE | DESC01 | DESC02 | DESC03 | DESC04-10 |
|---|---|---|---|---|---|
| 72015 | 4.80 | 0.05 | 0.04 | 0.04 | 0 |

```
PRECIO_NETO = 4.80 × (1-0.05) × (1-0.04) × (1-0.04) = 4.80 × 0.95 × 0.96 × 0.96 = 4.22006
```
