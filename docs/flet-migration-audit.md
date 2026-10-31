# Auditoría de compatibilidad Flet 0.85.2 → 1.0.5

> Auditoría read-only. No se modificó código de la aplicación.
> Fecha: 2026-10-30 · Rama base: `main` (0.85.2, 1725 tests verdes).

## 1. Versiones

| Item | Actual | Objetivo |
|---|---|---|
| `flet[desktop]` | `==0.85.2` | `>=1.0.5` |
| Python | `>=3.12` | sin cambio |
| uv.lock | flet 0.85.2 | flet 1.0.5 |

## 2. Inventario de controles Flet usados

Controles (mayúsculas) con mayor uso. Todos existen en 1.0.5 salvo los marcados.

| Control | Usos | Nota 1.0.5 |
|---|---|---|
| Text, Container, Row, Column | 302/157/148/99 | sin cambio |
| Icons, Colors, Padding, Border, Margin | 155/73/63/35/2 | sin cambio |
| FilledButton, TextButton, OutlinedButton, IconButton | 36/30/9/13 | sin cambio |
| AlertDialog | 14 | sin cambio |
| DatePicker | 4 | `on_change` sigue válido |
| RadioGroup, Radio, Checkbox | 3/14/11 | sin cambio |
| DataTable, DataColumn, DataRow, DataCell | 7/14/7/17 | `on_sort` sigue válido |
| Tabs, Tab | 7/6 | **cambia**: `Tabs(content=Column([TabBar, TabBarView]), length=N)`, `Tab(label=)` |
| SnackBar | 2 | **cambia**: sin `.open`; se muestra con `page.show_dialog(...)` |
| FilePicker, FilePickerFileType | 1/1 | servicio; `pick_files` async devuelve lista (ya migrado) |
| Theme, ThemeMode, AppView | 1/3/1 | sin cambio |
| ft.app | 1 | **cambia**: `ft.app(...)` → `ft.run(main)` |

Enums/helpers: `FontWeight`, `CrossAxisAlignment`, `MainAxisAlignment`, `ScrollMode`, `TextAlign`, `BoxFit`, `KeyboardType`, `TextOverflow`, `AnimationCurve`, `MouseCursor`, `RoundedRectangleBorder`, `BoxShadow`, `Chip`, `GestureDetector`, `ProgressBar`, `ProgressRing`, `Image`, `Wrap`, `Divider`, `TextField`. Todos válidos en 1.0.5.

## 3. Inventario de API de página

| API | Usos | 0.85 | 1.0.5 |
|---|---|---|---|
| `page.update()` | 94+47 | ✅ | ✅ |
| `page.open(x)` | 18 | ❌ (shim) | ✅ nativo → `page.show_dialog(x)` |
| `page.close(x)` | 26 | ❌ (shim) | ✅ nativo → `page.pop_dialog()` |
| `ctrl.open = True/False` | 4 | shim | se retira (dialogs no usan `.open`) |
| `page.add(...)` | 3 | ✅ | ✅ |
| `page.overlay` | 2 | ✅ | ✅ |
| `page.services` | 1 | ✅ | ✅ |
| `page.run_task(...)` | 1 | ✅ | ✅ |
| `page.run_thread(...)` | varios | ✅ | ✅ |
| `page.snack_bar.open = True` | 2 | ✅ | ❌ → `page.show_dialog(SnackBar(...))` |
| `page.window.resizable/title/...` | 6 | ✅ | ✅ (sigue) |
| `page.theme`, `page.theme_mode`, `page.bgcolor`, `page.padding` | 1 c/u | ✅ | ✅ |
| `page.on_resized` | 0 | n/a | n/a (no usado) |
| `ft.app(target=main, view=...)` | 1 | ✅ | ❌ → `ft.run(main, view=...)` |

## 4. Incompatibilidades detalladas (0.85 → 1.0.5)

### A. Diálogos (18 `page.open` + 26 `page.close` + 4 `ctrl.open`)

Archivos: `src/ui/view_panels.py` (mayoría), `src/ui/reporte_panel.py`, `src/ui/template_dialog.py`, `src/ui/view_handlers.py`, `src/ui/widgets/cliente_picker.py`.

Mapeo mecánico:
- `page.open(dlg)` → `page.show_dialog(dlg)`
- `page.close(dlg)` → `page.pop_dialog()`
- `dlg.open = True/False` → se elimina (el dialog se muestra/oculta por el método).

### B. SnackBar (2 usos en `src/core/g360_theme.py`, 1 en `main.py`)

- `page.snack_bar = ft.SnackBar(...); page.snack_bar.open = True; page.update()`
- → `page.show_dialog(ft.SnackBar(...))` o `page.open(ft.SnackBar(...))`.

### C. Tabs (7 `ft.Tabs`, 6 `ft.Tab`)

`src/ui/view_handlers.py` (`_TabsShim`, `_construir_tabs`, `_mostrar_tab_vacio`, `_insertar_en_tab`).

- En 1.0: `Tabs(selected_index=..., length=N, content=Column([TabBar(tabs=[Tab(label=...)]), TabBarView(controls=[...])]))`.
- `Tab(text=...)`/`Tab(content=...)` → `Tab(label=...)`.
- `.tabs[idx].content = x` → manipular `TabBarView.controls[idx]`.
- `on_change` sigue existiendo (Event.data = índice).

### D. Entry point (`main.py:1320`)

- `ft.app(...)` → `ft.run(main, ...)`.

### E. FilePicker (ya migrado en esta base)

- `FilePicker` como servicio en `page.services` ✅ (válido en 1.0).
- `pick_files()` async devuelve lista ✅ (válido en 1.0).
- `on_result` callback sigue existiendo en 1.0 (opcional).

### F. `ft.dropdown` (minúsculas, 26 usos)

Módulo helper `ft.dropdown`, no control. Verificar que sigue existiendo en 1.0 (probable, es un namespace). Confirmar en la implementación.

### G. `page.on_resized` (0 usos) — no aplica.

## 5. Componentes que NO necesitan cambios (evitar duplicación)

Text, Container, Row, Column, Icons, Colors, Padding, Border, Margin, FilledButton, TextButton, OutlinedButton, IconButton, AlertDialog, DatePicker, Radio/RadioGroup/Checkbox, DataTable/DataColumn/DataRow/DataCell, Theme/ThemeMode, Image, ProgressBar/ProgressRing, Chip, Divider, GestureDetector, TextField, Wrap, Animation*, ButtonStyle, RoundedRectangleBorder, BoxShadow, MouseCursor, ScrollMode, Alignment, BoxFit, TextAlign, FontWeight, KeyboardType, TextOverflow, FilePickerFileType, AppView, ThemeMode.

Total ≈ 35 controles/enums sin cambios.

## 6. Componentes que SÍ necesitan cambios (priorizados)

| # | Componente | Archivos | Riesgo | Esfuerzo |
|---|---|---|---|---|
| 1 | Entry point `ft.app` → `ft.run` | `main.py` | Bajo | 1 línea |
| 2 | `page.open`/`page.close` dialogs | `view_panels.py`, `reporte_panel.py`, `template_dialog.py`, `view_handlers.py`, `cliente_picker.py` | Bajo | 44 reemplazos mecánicos |
| 3 | SnackBar `.open` | `g360_theme.py`, `main.py` | Bajo | 2-3 cambios |
| 4 | FilePicker (validar firma) | `main.py` | Bajo | ya migrado; verificar `on_upload` |
| 5 | Tabs (shim → nativo) | `view_handlers.py` | Alto | reescribir `_mostrar_tab_vacio`/`_insertar_en_tab` |
| 6 | Renderer desktop (ventana/overlay/services) | `main.py` | Alto | validar arranque real + empaquetado |

## 7. Dependencias (pyproject.toml)

```
flet[desktop]==0.85.2   ->   flet[desktop]>=1.0.5
```

Sin otras dependencias afectadas (pandas, openpyxl, pydantic, etc. no dependen de flet).

## 8. Plan por componente (según directiva)

Para cada componente del §6, en orden:

1. Crear rama `feat/flet105-<componente>` en worktree `projects/.trees/g360-erp-nc-sustentor/feat-flet105-<componente>`.
2. Instalar flet 1.0.5 en el venv del worktree (`uv sync` con override).
3. Analizar archivo/clase/función/propiedad/evento/import del original.
4. Documentar incompatibilidades (este doc).
5. Crear implementación v2 al lado (`*_105.py`), sin tocar el original.
6. Test aislado + integración en el worktree.
7. Validar arranque real en desktop.
8. Solicitar validación antes de sustituir.
9. Commit por componente (rollback por componente).

## 9. Riesgos y rollback

- **Riesgo alto**: Tabs (cambia API de manipulación de contenido). Mitigación: mantener `_TabsShim` hasta que el v2 pase tests + arranque real.
- **Riesgo medio**: dialogs mecánicos (44 reemplazos). Mitigación: script de reemplazo + tests de UI.
- **Rollback**: cada componente en commit separado; `git revert <commit>` por componente. La base 0.85.2 queda intacta en `main`.
- **No monkey-patches en la versión definitiva 1.0.5**: el shim `page.open`/`page.close` se retira al completar el componente #2.

## 10. Criterio de aceptación por componente

Un componente se considera migrado cuando:
- Supera sus pruebas (unitarias + integración).
- Conserva comportamiento original (comparación visual/funcional).
- Funciona en la app real (arranque desktop + flujo).
- No introduce regresiones en otros módulos (suite completa verde).

La migración completa finaliza tras validar: navegación, diálogos, archivos, notificaciones, renderer y empaquetamiento a `.exe`.

## Próximo paso propuesto

Componente #1 (entry point `ft.app` → `ft.run`): trivial, 1 línea, sin riesgo. ¿Arranco por ahí en el worktree `feat-flet105-entrypoint`?