# Migración Flet — Estado y Guía

## Versión actual

- **pyproject.toml**: `flet[desktop]>=1.0`
- **uv.lock**: `flet==1.0.5`
- **venv instalado**: `flet==1.0.5`
- **Tests**: ~1540 passed, ~150 fallan por API changes

## Cambios de API Flet 0.85 → 1.0.5

| API Vieja | API Nueva | Estado |
|---|---|---|
| `ft.ElevatedButton` | `ft.FilledButton` | ✅ Migrado |
| `ft.padding.*()` | `ft.Padding.*()` | ✅ Migrado |
| `ft.margin.*()` | `ft.Margin.*()` | ✅ Migrado |
| `ft.border.*()` | `ft.Border.*()` | ✅ Migrado |
| `ft.Alignment.center` | `ft.alignment.Alignment(0, 0)` | ✅ Migrado |
| `Dropdown.on_change` | `Dropdown.on_select` | ✅ Migrado |
| `DatePicker.on_change` | `DatePicker.on_change` | ⚠️ Revertir a `on_change` |
| `RadioGroup.on_change` | `RadioGroup.on_change` | ✅ Correcto |
| `Checkbox.on_change` | `Checkbox.on_change` | ✅ Correcto |

## Archivos modificados

- `src/core/g360_theme.py`
- `src/ui/view_panels.py`
- `src/ui/view_handlers.py`
- `src/ui/resultados_view.py`
- `src/ui/reporte_panel.py`
- `src/ui/reporte_compras.py`
- `src/ui/widgets/control_factory.py`
- `src/ui/widgets/workflow_section.py`
- `tests/*.py` (varios)

## Próximos pasos

1. Revertir `DatePicker.on_select` → `on_change` en view_panels.py
2. Buscar otros `on_select` que deban ser `on_change`
3. Ejecutar tests completos
4. Commit de la migración
