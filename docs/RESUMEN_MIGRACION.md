# Resumen de Migración Flet 0.28 → 1.0.5

## Estado Final: ✅ COMPLETADO

### Version
- **pyproject.toml**: `flet[desktop]>=1.0.5`
- **Versión app**: `1.2.2`

### Tests
```
uv run pytest -q
# 1725 passed, 13 warnings (pandas FutureWarning, no relacionados)
```

---

## Cambios Realizados

### 1. Migración API Flet 1.0.5

| Cambio | Antes (0.28) | Ahora (1.0.5) | Estado |
|--------|--------------|---------------|--------|
| Entry point | `ft.app(target=main)` | `ft.run(main)` | ✅ |
| FilePicker | Control en overlay | Servicio en `page.services` | ✅ |
| Pick files | Callback `on_result` | Async con `page.run_task` | ✅ |
| SnackBar | `page.snack_bar.open` | `page.show_dialog(SnackBar)` | ✅ |
| Diálogos | `page.open/close` | `page.show_dialog/pop_dialog` | ✅ |
| Estilos | `ft.padding.*()`, `ft.border.*()` | `ft.Padding.*`, `ft.Border.*` | ✅ |
| Image fit | `ft.ImageFit.CONTAIN` | `ft.BoxFit.CONTAIN` | ✅ |
| Botones | `ft.ElevatedButton` | `ft.FilledButton`/`OutlinedButton` | ✅ |
| Tabs | `ft.Tabs` antiguo | `ft.TabBar`/`ft.TabBarView` | ✅ |

### 2. Inspección Liviana (Feature Nueva)

**Archivo**: `src/core/capture_service.py`

Cuando `MAX(fecha_orig) == hoy`, antes de descargar:
1. Consulta conteo local de filas para hoy
2. Sonda portal con GET L0 (`count_grid_rows`)
3. Si conteos coinciden → omite hoy (no baja nada)
4. Si difieren → captura normalmente
5. Si falla cualquier paso → incluye hoy por seguridad

**Método nuevo**: `IntranetClient.count_grid_rows(desde, hasta) -> int`
- GET L0 del día
- Extrae filas sin descargar export completo
- Devuelve conteo de filas de datos

**Seguridad**:
- Nunca rompe si falla
- No sobreescribe datos existentes
- No duplica (DELETE+INSERT diario ya existente)

### 3. Limpieza del Repo

| Archivo/Elemento | Acción |
|------------------|--------|
| `probe_*.py` | Eliminados |
| `smoke_db.py` | Eliminados |
| `*_err.txt`, logs | Eliminados |
| `src/ui/panels/gestion.py` | Eliminados (placeholders vacíos) |
| `src/ui/panels/busqueda.py` | Eliminados (placeholders vacíos) |
| `_on_picker_generic` | Eliminados (código muerto) |
| `_picker_callback`, `_picker_files_callback` | Eliminados |
| Bloques duplicados en `_build_header` | Limpiados |

### 4. Documentación

| Archivo | Contenido |
|---------|-----------|
| `docs/inspeccion-liviana.md` | Explicación detallada de la feature |
| `docs/CHANGELOG.md` | Historial de cambios |
| `docs/flet-migration.md` | Actualizado con estado ✅ |
| `README.md` | Versión actualizada a 1.2.2 |

---

## Verificación de Paridad con Producción

| Aspecto | Portable (0.28.3) | Dev (1.0.5) | Veredicto |
|---------|-------------------|-------------|-----------|
| Arranque | `ft.app()` | `ft.run()` | ✅ Mejora |
| FilePicker | Callback antiguo | Async moderno | ✅ Mejora |
| SnackBar | `open=True` | `show_dialog` | ✅ Mejora |
| Tema/Colores | Hardcodeados | Tokens CIPSA | ✅ Mejora |
| Tabs | API antigua | `TabBarView` | ✅ Mejora |
| **Inspección liviana** | No existe | Implementado | ✅ **NUEVO** |
| Tests | - | 1725 passing | ✅ **VERIFICADO** |

---

## Pendiente Menor (No Bloqueante)

| Punto | Estado |
|-------|--------|
| `view_panels.py:5614` usa `page.run_thread` | Funciona, por coherencia podría migrarse a `run_task` |
| Código de header | Limpiado, solo un bloque vivo |

---

## Comandos de Verificación

```bash
# Tests específicos de inspección
uv run pytest tests/test_inspeccion_liviana.py -v

# Tests de contraste/tema
uv run pytest tests/test_contraste.py tests/test_tema_contraste.py -v

# Suite completa
uv run pytest -q
```

---

**Conclusión**: La migración está completa y el repo de desarrollo supera a producción en funcionalidad (inspección liviana) y mantenibilidad (código limpio, tests completos).
