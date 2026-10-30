"""Panel de gestión: export/import de cartuchos y config de DB local.

Contendrá eventualmentela sección que hoy vive dentro de `_panel_gestion`
en ``view_panels.py``. Por ahora es un placeholder.

Estructura prevista:
  - helpers de cartucho (path, nombres, validación)
  - fábrica de controles (botones, previews, confirmaciones)
  - clase GestionPanel que expone el árbol de controles
  - handlers: elegir_archivo, elegir_cartucho, reemplazar, importar, exportar

Migración: ver ``ROADMAP.md`` en la raíz del paquete para el orden de
movimiento de cada handler.
"""

# TODO: migrar desde view_panels._panel_gestion
# - helpers puros: elegir_archivo, elegir_cartucho, reemplazar
# - fábrica de controles: botones de export/import, previews
# - clase GestionPanel con _construir_layout interno
# - handlers integrados: _exportar_cartucho, _abrir_export, _importar_cartucho

__all__ = []
