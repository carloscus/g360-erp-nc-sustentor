"""Verificación headless de la sección Datos del caso: chips de cliente/
pedido/O-C/factura, botones documentales y geometría del card de búsqueda."""

import flet as ft

from src.core.g360_theme import G360Theme
from src.core.fechas import fecha_ui
from src.ui.reconocimiento_view import ReconocimientoView


class _App:
    page = None
    G360_ACCENT = G360Theme.accent_color()
    G360_SUCCESS = G360Theme.ok_color()
    G360_WARNING = G360Theme.warning_color()
    G360_ERROR = G360Theme.error_color()
    G360_ACCENT_2 = G360Theme.accent_2_color()

    def show_snackbar(self, *args, **kwargs):
        pass

    def show_loading(self, *args, **kwargs):
        pass

    def hide_loading(self, *args, **kwargs):
        pass

    def _pick_files(self, *args, **kwargs):
        return []

    def _pick_file(self, *args, **kwargs):
        return None

    def _get_desktop_path(self):
        from pathlib import Path

        return Path.cwd()


def _vista(tmp_db):
    view = ReconocimientoView(_App())
    view.build()
    return view


def _labels(row):
    return [c.label.value for c in row.controls if isinstance(c, ft.Chip)]


def _textos(control):
    out = []
    value = getattr(control, "value", None)
    if isinstance(value, str):
        out.append(value)
    for child in getattr(control, "controls", None) or []:
        out.extend(_textos(child))
    content = getattr(control, "content", None)
    if content is not None:
        out.extend(_textos(content))
    return out


def test_chips_ocultos_al_construir(tmp_db):
    view = _vista(tmp_db)
    for row in (view.busq_cli_chips, view.busq_ped_chips, view.busq_oc_chips, view.busq_fac_chips):
        assert row.visible is False
        assert row.controls == []
        assert row.scroll == ft.ScrollMode.AUTO


def test_chips_por_tipo_con_on_delete(tmp_db):
    view = _vista(tmp_db)
    view._sel_clientes = [("00056101", "MULTICOPIAS MARY E.I.R.L.")]
    view._sel_facturas = [("00056101", "F204-67375")]
    view._sel_pedidos = [("00056101", "P-100")]
    view._sel_ordenes = [("00056101", "OC-200")]
    view.btn_pin_cli.on_click(None)  # dispara _pintar_chips + _refresh_doc_buttons

    assert _labels(view.busq_cli_chips) == ["MULTICOPIAS MARY E.I.R.L. (56101)"]
    assert _labels(view.busq_ped_chips) == ["Pedido · P-100"]
    assert _labels(view.busq_oc_chips) == ["O/C · OC-200"]
    assert _labels(view.busq_fac_chips) == ["F204-67375"]
    for row in (view.busq_cli_chips, view.busq_ped_chips, view.busq_oc_chips, view.busq_fac_chips):
        assert row.visible is True
        for chip in row.controls:
            assert chip.on_delete is not None
            assert chip.delete_icon_color == G360Theme.error_color()


def test_botones_documentales_solo_con_disponibles(tmp_db):
    view = _vista(tmp_db)
    view._sel_clientes = [("00056101", "MULTICOPIAS MARY E.I.R.L.")]
    view._detalle_docs = {"00056101": {"pedidos": 2, "ordenes": 0, "facturas": 3}}
    view.btn_pin_cli.on_click(None)

    assert view.busq_doc_row.visible is True
    assert view.busq_doc_ped_btn.visible is True
    assert view.busq_doc_ped_btn.content.value == "Pedidos · 2"
    assert view.busq_doc_oc_btn.visible is False
    assert view.busq_doc_fac_btn.visible is True
    assert view.busq_doc_fac_btn.content.value == "Facturas · 3"
    assert view.busq_doc_prompt.visible is False


def test_botones_documentales_con_prompt_sin_cliente(tmp_db):
    view = _vista(tmp_db)
    view.btn_pin_cli.on_click(None)
    assert view.busq_doc_row.visible is False
    assert view.busq_doc_prompt.visible is True
    assert "Selecciona un cliente" in view.busq_doc_prompt.value


def test_geometria_del_card_de_busqueda(tmp_db):
    view = _vista(tmp_db)
    # Preview acotado y dropdown sin expand (wrap=True rompe con hijos expandidos).
    assert view.busq_preview_tbl.height == 170
    assert view.busq_preview_tbl.visible is False
    assert view.busq_vend_dd.width == 260
    assert view.busq_vend_dd.visible is False
    assert view.busq_exec_btn.visible is False
    # Filas de filtros con wrap (sin overflow en 960 de min_width).
    assert view.busq_doc_row.scroll == ft.ScrollMode.AUTO


def test_picker_modal_sin_pagina_no_crashea(tmp_db):
    view = _vista(tmp_db)
    view._sel_clientes = [("00056101", "MULTICOPIAS MARY E.I.R.L.")]
    # page=None → el picker retorna temprano sin abrir el modal.
    view.busq_doc_ped_btn.on_click(None)
    view.busq_doc_oc_btn.on_click(None)
    view.busq_doc_fac_btn.on_click(None)


def test_rango_fechas_se_preserva_entre_renders(tmp_db):
    """El rango elegido no se resetea a últimos 30 días al re-renderizar
    (cambio de caso / aplicar fragmento)."""
    from datetime import datetime

    view = _vista(tmp_db)
    view.busq_fd[0] = datetime(2026, 5, 1)
    view.busq_fh[0] = datetime(2026, 5, 31)
    view._renderizar_ui()
    assert view.busq_fd[0] == datetime(2026, 5, 1)
    assert view.busq_fh[0] == datetime(2026, 5, 31)
    assert fecha_ui(datetime(2026, 5, 1)) in view.busq_fd_label.value
    assert fecha_ui(datetime(2026, 5, 31)) in view.busq_fh_label.value


def test_selector_multicliente_usa_on_select(tmp_db):
    """Con 2+ clientes aparece el selector, y su evento es `on_select`.

    En Flet 1.0.5 `Dropdown` no acepta `on_change`: pasarlo revienta el
    constructor y la card "Datos del caso" no se arma (regresión real, vista
    por primera vez en `test_simulacion_flujos`).
    """
    view = _vista(tmp_db)
    view._sel_clientes = [
        ("00023307", "MULTICOPIAS MARY E.I.R.L."),
        ("00056101", "CLIENTE CON COMPRAS"),
    ]
    view.btn_pin_cli.on_click(None)

    dd = view.busq_cli_selector
    assert isinstance(dd, ft.Dropdown)
    assert dd.visible is True
    assert [o.key for o in dd.options] == ["00023307", "00056101"]
    assert dd.value == "00056101"  # el último agregado queda activo
    assert dd.on_select is not None


def test_selector_multicliente_se_oculta_con_uno(tmp_db):
    view = _vista(tmp_db)
    view._sel_clientes = [
        ("00023307", "MULTICOPIAS MARY E.I.R.L."),
        ("00056101", "CLIENTE CON COMPRAS"),
    ]
    view.btn_pin_cli.on_click(None)
    assert view.busq_cli_selector.visible is True

    view._sel_clientes = [("00023307", "MULTICOPIAS MARY E.I.R.L.")]
    view.btn_pin_cli.on_click(None)
    assert view.busq_cli_selector.visible is False


def test_insumos_cargados_sobreviven_re_render(tmp_db):
    """Los archivos añadidos (y su preview) persisten al reconstruir la card."""
    view = _vista(tmp_db)
    view._insumo_files = [
        {
            "ruta": r"C:\x\lista.xlsx",
            "tipo": "lista_precios",
            "lbl": "lista.xlsx",
            "preview": None,
            "preview_loading": True,
        }
    ]
    view._renderizar_ui()
    assert len(view._insumo_files) == 1
    assert view.insumo_list_wrapper.visible is True
    assert "lista.xlsx" in _textos(view.insumo_list_wrapper)
    # La fila del archivo re-renderizada con su botón quitar.
    filas = view.insumo_list.controls
    assert any(
        isinstance(c, ft.Container)
        and isinstance(c.content, ft.Row)
        and any(isinstance(ch, ft.IconButton) for ch in c.content.controls)
        for c in filas
    )
