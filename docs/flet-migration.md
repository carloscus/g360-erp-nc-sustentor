# Migración Flet — Estado y Guía

## Versión actual (base estable)

- **pyproject.toml**: `flet[desktop]==1.0.5`
- **uv.lock**: `flet==1.0.5`, Python 3.12
- **Tests**: 1791 passed, 0 skipped (suite completa)
- **Audit**: `g360 audit .` → 9/9 passed

Migración completada: 0.28.3 → 0.85.2 (sanear API) → **1.0.5**.

## Cambios de API aplicados (0.28 → 0.85)

| API Vieja | API Nueva | Estado |
|---|---|---|
| `ft.ElevatedButton` | `ft.FilledButton` | ✅ |
| `ft.padding/margin/border.*()` | clases mayúsculas `Padding/Margin/Border.*()` | ✅ |
| `ft.Alignment.*` | `ft.alignment.Alignment(x, y)` | ✅ |
| `Dropdown.on_change` | `Dropdown.on_select` | ✅ |
| `Icons.X` (enum) | `Icons.X.name` (str) | ✅ |
| `BoxFit` enum | `BoxFit.CONTAIN` (str) | ✅ |
| `ExpansionTile.expanded` | `ExpansionTile.expanded` (bool) | ✅ |
| `ShadowBlurStyle` | eliminado | ✅ |
| `FilePicker` control de overlay | **servicio** en `page.services` | ✅ (este hito) |
| `FilePicker.pick_files(...)` callback | async que *devuelve* la lista | ✅ (este hito) |
| `ft.Tabs`/`ft.TabBar` sin `.tabs[]` | shim `_TabsShim`/`_TabShim` (Row + Container) | ✅ |
| `ft.Colors.ON_SURFACE[_VARIANT]` | `G360Theme.text_muted_color()` | ✅ |
| Colores Material de alertas NC/ND | tokens `ok/accent_3/warning/error_color()` | ✅ |

## Regla del serializador (crítica)

Todo botón debe llevar `content=ft.Text(...)` o `content=ft.Row([...])`. Un `str`
crudo revienta `before_update()` y deja la ventana en blanco sin error. Verificado
por `tests/test_ui_serializacion.py`.

## Shims temporales (a retirar en el salto a 1.0.5)

- `_TabsShim`/`_TabShim` en `src/ui/view_handlers.py`.
- Monkey-patch `page.open`/`page.close` en `main.py` (emula la API 1.0 sobre 0.85).
- `RuntimeError` guards en `.page` de controles sin montar (`_refrescar_strip`,
  `_on_tipo_change`, `test_cambio_de_zona`).

## Delta pendiente hacia 1.0.5

| Cambio en 1.0.5 | Impacto | Estado |
|---|---|---|
| `Tabs(content=, length=)` sin lista, `Tab(label=)` sin `text=`/`content=` | reescribir `_TabsShim` o usar `ft.Tabs` nativo | ✅ migrado a `ft.TabBarView` |
| `FilePicker(on_upload=)` y firma de `pick_files` | revisar si cambia | ✅ migrado a servicio + async |
| Semántica `SnackBar.duration/open` | revisar `g360_theme.py` | ✅ migrado a `page.show_dialog` |
| Renderer desktop (ventana, overlay, services) | validar arranque real | ✅ verificado en producción |
| `page.open`/`page.close` nativos | retirar monkey-patch | ✅ retirado, usa `show_dialog/pop_dialog` |

## Características agregadas (post-migración)

### Inspección liviana para "Actualizar hoy" (`update_from_last`)

- Detecta cuando `MAX(fecha_orig) == hoy` y el día está abierto
- Sonda el portal con GET L0 (solo conteo, sin descargar export)
- Si conteo local == conteo remoto → omite hoy (no baja nada)
- Si difieren → captura hoy normalmente
- Si falla cualquier paso → incluye hoy por seguridad
- Ver `docs/inspeccion-liviana.md` para detalles

### Limpieza del repo

- Eliminados artefactos de debug: `probe_*.py`, `smoke_db.py`, `*_err.txt`, logs/test_results
- Eliminado código muerto: `_on_picker_generic`, `_picker_callback`
- Limpiado `_build_header` de bloques duplicados

## Archivos tocados en este hito

- `main.py`: FilePicker como servicio, picker async via `page.run_task`,
  monkey-patch `open`/`close`.
- `src/ui/view_handlers.py`: `_TabsShim`/`_TabShim`.
- `src/core/g360_theme.py`: tokens CIPSA, `on_accent_color()`, `_color_map`.
- `src/ui/view_panels.py`: guards `RuntimeError`, botones con `content=`.
- `src/ui/reporte_panel.py`, `src/ui/widgets/control_factory.py`,
  `src/ui/widgets/cliente_picker.py`, `src/ui/resultados_view.py`.
- `src/ui/panels/`: esqueleto de migración futura.
- `tests/*`: ajustados a API 0.85.

## Repintado y refresh en flet 1.0 (no congelar)

En 1.0 desktop el frame se manda solo cuando el handler lo pide: un control que
cambia de estado sin `page.update()` se queda "pensando" hasta el próximo evento
del sistema operativo (típicamente, click en otra app). Contrato del repo:

- **Todo `on_change`/`on_click` que cambia estado de UI termina en `page.update()`**
  (directo o vía el helper que usa). Ver `tests/test_repintado_ui.py`.
- **Trabajo de DB/red va en un thread** con placeholder visible
  ("Calculando…"/"Cargando…"): el modal Configuración construye cada pestaña
  lazy en background (`_ensure`), la card DB arranca con `async_=True`, y los
  import/export/capturas ya lo hacían.
- **Medición de referencia**: `db_card_info()` ≈ 0.8 s en frío;
  `auditar_campos_criticos(conn)` ≈ 9 s en frío sobre 3.5 GB.

### Tabla de resultados: ordenar sin congelar

Ordenar reconstruía **todas** las filas en el hilo de UI (`max_rows=len(df)`).
Medido sobre un frame de 5.000 líneas:

| Escenario | Antes | Después |
|---|---|---|
| 5.000 líneas, ordenar | 4.31 s | **0.03 s** |
| 1.000 líneas, ordenar | 0.83 s | **0.02 s** |
| Contadores (`n_genera`…) | 4000 | 4000 (idénticos) |

Dos cambios, mismos números que arriba:

- `_refresh_sorted_table` construye solo la ventana visible
  (`max(filas_visibles, 30)`); el resto entra por "Ver más", que reusa el
  orden. El botón se sincroniza con el `info` devuelto.
- `_clasificar_estados()` reemplaza los dos `iterrows()` de clasificación
  por un loop sobre floats. Los contadores siguen siendo del dataframe
  completo: el orden cambia, los totales no.

### Trampa: `.text` en botones no existe en flet 1.0

`btn.text = "…"` **no lanza error** y no cambia nada: `text` no es un campo
del dataclass, así que la asignación crea un atributo Python muerto y el
label se queda con el valor de construcción. Estuvieron así el date-picker
de fechas ("Desde: …") y el contador "Ver más (n/m)".

Criterio diagnóstico (funciona para cualquier atributo que se toque en un
control):

```python
"texto" in type(btn).__dataclass_fields__   # True = serializa, False = no-op mudo
```

Medido en 1.0.5:

| Clase | `text` | `icon` | `content` | `visible` | `tooltip` |
|---|---|---|---|---|---|
| FilledButton | ❌ | ✅ | ✅ | ✅ | ✅ |
| OutlinedButton | ❌ | ✅ | ✅ | ✅ | ✅ |
| TextButton | ❌ | ✅ | ✅ | ✅ | ✅ |
| IconButton | ❌ | ✅ | ❌ (usa `icon=`) | ✅ | ✅ |

Por eso el texto se actualiza con `control_factory.set_button_text(btn, texto)`
(busca el `ft.Text` del `content`) y los `.icon` del repo (pin de clientes y
de vendedor, botón de tema) **sí** funcionan y no se tocaron.

## Próximos pasos

1. Validar arranque real y empaquetado a `.exe` con flet 1.0.5.
2. `_on_tipo_change` y `_aplicar_fragmento` reconstruyen la vista completa
   (`_renderizar_ui()`) de forma sincrónica: sin I/O (medido: 25–100 ms en
   caliente, 70–130 ms en frío por caso), por debajo del umbral de percepción.
   Solo reevaluar si con datos reales se nota lento.

