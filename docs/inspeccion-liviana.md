# Inspección Liviana — Actualizar hoy

## Problema

El flujo `update_from_last()` usa `MAX(fecha_orig)` como criterio para decidir si hay trabajo pendiente.
Si el último registro tiene fecha == hoy, el día se considera "cerrado" y se retorna `filas: 0`.

**Problema**: si después de la última captura se subieron nuevos documentos con fecha hoy al portal,
esa inspección los pasa por alto y quedan sin capturar.

## Solución

Se agregó un paso de **inspección liviana** antes de planificar chunks:

1. **Si `fmax == hoy` y el día está abierto** → consulta conteo local de `ventas` para hoy
2. **Sonda el portal** con `IntranetClient.count_grid_rows()` (GET L0, extrae filas sin descargar export)
3. **Si conteos coinciden** → `dias` pierde el día de hoy, retorna `filas: 0` inmediatamente
4. **Si difieren** → hoy permanece en `dias`, se captura normalmente
5. **Si cualquier paso falla** → hoy se incluye por seguridad (never break on error)

## Implementación

### `src/core/intranet_client.py`

Método nuevo `count_grid_rows(desde, hasta) -> int`:
- GET L0 (grid HTML) del día
- Extrae filas con `extract_grid_devexpress()` o fallback a `extract_largest_table_html()`
- Devuelve `len(rows) - 1` (resta header)

### `src/core/capture_service.py`

En `update_from_last()`, después de calcular `dias`, antes de retornar early:
- Solo aplica cuando `fmax == hoy` y `dias` contiene `hoy`
- Requiere credenciales; si no hay, incluye hoy por defecto
- Todo envuelto en try/except: fallo = incluir hoy
- Log de plan actualizado con resultado de la inspección

## Seguridad

- **Nunca rompe si falla**: cualquier excepción deja `dias` intacto
- **No sobreescribe**: si los conteos difieren, el día se procesa con DELETE+INSERT diario existente
- **No duplica**: el día ya tenía checksum previo; el proceso normal maneja todo
- **No afecta días anteriores**: solo hoy es inspeccionado livianamente; días del overlap siguen su curso normal

## Logs

- `"Inspección liviana: portal=N, local=N → sin cambios, omitiendo hoy"`
- `"Inspección liviana: portal=N, local=M → difiere, se incluirá hoy"`
- `"inspección liviana fallo (...); se incluye hoy por seguridad"`
