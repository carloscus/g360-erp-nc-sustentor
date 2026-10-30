"""Panel de búsqueda y fragmento de historial.

Este submódulo contendrá eventualmentela sección que hoy vive dentro de
`_construir_seccion_datos` en ``view_panels.py``. Por ahora es un placeholder
que permite importar el paquete sin romper dependencias externas.

Estructura prevista:
  - constantes y helpers puros (formato de fechas, rangos)
  - fábrica de controles (pickers, chips, botones)
  - clase ``BusquedaPanel`` que expone el árbol de controles del panel
  - funciones de integración (_busq_executar, _pintar_resultado_busqueda, etc.)

Migración: ver ``ROADMAP.md`` en la raíz del paquete para el orden de
movimiento de cada helper.
"""

# TODO: migrar desde view_panels._construir_seccion_datos
# - helpers puros: _rango_str, _fmt_fecha (ya inlineado), validadores
# - fábrica de controles: pickers de cliente/factura/pedido/orden
# - clase BusquedaPanel con _construir_layout interno
# - handlers de integración: _busq_executar, _pintar_resultado_busqueda

__all__ = []
