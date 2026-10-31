# Migración Flet — Estado y Guía

## Versión actual (base estable)

- **pyproject.toml**: `flet[desktop]==0.85.2`
- **uv.lock**: `flet==0.85.2`
- **venv instalado**: `flet==0.85.2`
- **Tests**: 1725 passed, 13 warnings (`uv run pytest -q -p no:cacheprovider`, ~6:30 min)
- **Audit**: `g360 audit .` → 9/9 passed

El salto directo a 1.0.5 rompió ~150 tests; se adoptó la estrategia etapada
0.28.3 → 0.85.2 (sanear API) → 1.0.5. Hoy estamos en la base 0.85.2.

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
| `Tabs(content=, length=)` sin lista, `Tab(label=)` sin `text=`/`content=` | reescribir `_TabsShim` o usar `ft.Tabs` nativo | ⏳ |
| `FilePicker(on_upload=)` y firma de `pick_files` | revisar si cambia | ⏳ |
| Semántica `SnackBar.duration/open` | revisar `g360_theme.py` | ⏳ |
| Renderer desktop (ventana, overlay, services) | validar arranque real | ⏳ |
| `page.open`/`page.close` nativos | retirar monkey-patch | ⏳ |

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

## Próximos pasos

1. Correr suite completa y `g360 audit .`.
2. Commit del hito "1725 verdes en Flet 0.85.2".
3. Reintentar `flet[desktop]>=1.0`: `uv lock --refresh` + `uv sync`,
   aplicar solo el delta restante (Tabs, FilePicker, SnackBar, renderer).
4. Si 1.0.5 queda verde: validar arranque real y empaquetado a `.exe`.
path">
C:\Users\ccusi\Documents\Proyect_Coder\G360-ecosystem\projects\g360-erp-nc-sustentor\docs\flet-migration.md