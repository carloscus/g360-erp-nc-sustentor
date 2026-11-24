"""Fondo y texto de inputs: deben seguir el tema al crearse y al cambiarlo.

Un text_field / dropdown creado en tema claro nace con el fondo claro
(surface_sunken_color() resuelto en la llamada) y con texto legible sobre
ese fondo. Al alternar el tema y volver, los controles existentes quedan con
el fondo del tema nuevo (apply_theme re-mapea el bgcolor literal congelado).
"""

from __future__ import annotations

import flet as ft
import pytest

from src.core.g360_theme import G360Theme
from src.ui.widgets import control_factory as cf


def _rel_luminance(color_hex: str) -> float:
    """Luminancia relativa WCAG de un color hex #RRGGBB."""
    c = color_hex.lstrip("#")
    r, g, b = (int(c[i : i + 2], 16) / 255.0 for i in (0, 2, 4))

    def s(channel: float) -> float:
        return channel / 12.92 if channel <= 0.03928 else ((channel + 0.055) / 1.055) ** 2.4

    return 0.2126 * s(r) + 0.7152 * s(g) + 0.0722 * s(b)


def _contraste_ratio(texto_hex: str, fondo_hex: str) -> float:
    """Ratio de contraste WCAG entre dos colores hex."""
    l1 = _rel_luminance(texto_hex)
    l2 = _rel_luminance(fondo_hex)
    if l1 > l2:
        return (l1 + 0.05) / (l2 + 0.05)
    return (l2 + 0.05) / (l1 + 0.05)


@pytest.fixture(autouse=True)
def _restaura_tema():
    """El tema es estado global de clase: ningun test puede dejarlo cambiado."""
    antes = G360Theme._is_dark
    yield
    G360Theme.set_theme_mode(antes)


class TestInputFondoSegunTema:
    def test_text_field_en_claro_tiene_fondo_claro(self):
        """T1: creado en claro, bgcolor == surface_sunken_color() de claro."""
        G360Theme.set_theme_mode(False)
        campo = cf.text_field("X")
        assert campo.bgcolor == G360Theme.surface_sunken_color()
        assert campo.bgcolor != G360Theme.SURFACE_SUNKEN

    def test_dropdown_en_claro_tiene_fondo_claro(self):
        """T1: creado en claro, bgcolor == surface_sunken_color() de claro."""
        G360Theme.set_theme_mode(False)
        dd = cf.dropdown("Y")
        assert dd.bgcolor == G360Theme.surface_sunken_color()
        assert dd.bgcolor != G360Theme.SURFACE_SUNKEN

    def test_input_no_hereda_fondo_del_tema_oscuro(self):
        """Si el modulo se importa en dark, un control creado en claro no usa el tono oscuro congelado."""
        G360Theme.set_theme_mode(True)
        _ = cf.text_field("dummy")  # fuerza COLOR_INPUT en valor dark
        G360Theme.set_theme_mode(False)
        campo = cf.text_field("X")
        assert campo.bgcolor == G360Theme.surface_sunken_color()
        assert campo.bgcolor != G360Theme.SURFACE_SUNKEN


class TestInputCambioDeTema:
    def test_control_existente_se_corrige_al_cambiar_tema(self):
        """T2: un control construido en dark se re-mapea a light con apply_theme."""
        G360Theme.set_theme_mode(True)
        campo = cf.text_field("SKU")
        oscuro = campo.bgcolor
        assert oscuro == G360Theme.SURFACE_SUNKEN
        G360Theme.set_theme_mode(False)
        G360Theme.apply_theme(campo)
        assert campo.bgcolor == G360Theme.surface_sunken_color()
        assert campo.bgcolor != oscuro

    def test_volver_a_dark_restaura_el_tono_original(self):
        """Ida y vuelta: el input vuelve a su tono dark original."""
        G360Theme.set_theme_mode(True)
        campo = cf.text_field("SKU")
        original = campo.bgcolor
        G360Theme.set_theme_mode(False)
        G360Theme.apply_theme(campo)
        G360Theme.set_theme_mode(True)
        G360Theme.apply_theme(campo)
        assert campo.bgcolor == original

    def test_dropdown_tambien_se_mueve_al_cambiar_tema(self):
        G360Theme.set_theme_mode(True)
        dd = cf.dropdown("Vendedor")
        oscuro = dd.bgcolor
        G360Theme.set_theme_mode(False)
        G360Theme.apply_theme(dd)
        assert dd.bgcolor == G360Theme.surface_sunken_color()
        assert dd.bgcolor != oscuro


class TestInputTextoLegible:
    def test_texto_de_text_field_es_legible_en_claro(self):
        """T4: el color de texto fijado tiene contraste suficiente sobre el fondo en claro."""
        G360Theme.set_theme_mode(False)
        campo = cf.text_field("X")
        ratio = _contraste_ratio(campo.color, campo.bgcolor)
        assert ratio >= 4.5, f"contraste insuficiente en claro: {ratio:.2f}"

    def test_texto_de_text_field_es_legible_en_oscuro(self):
        """T4: el color de texto fijado tiene contraste suficiente sobre el fondo en oscuro."""
        G360Theme.set_theme_mode(True)
        campo = cf.text_field("X")
        ratio = _contraste_ratio(campo.color, campo.bgcolor)
        assert ratio >= 4.5, f"contraste insuficiente en oscuro: {ratio:.2f}"

    def test_texto_de_dropdown_es_legible_en_claro(self):
        G360Theme.set_theme_mode(False)
        dd = cf.dropdown("Y")
        ratio = _contraste_ratio(dd.color, dd.bgcolor)
        assert ratio >= 4.5, f"contraste insuficiente en claro: {ratio:.2f}"

    def test_texto_de_dropdown_es_legible_en_oscuro(self):
        """El texto del dropdown en dark debe ser legible sobre su fondo hundido."""
        G360Theme.set_theme_mode(True)
        dd = cf.dropdown("Y")
        ratio = _contraste_ratio(dd.color, dd.bgcolor)
        assert ratio >= 4.5, f"contraste insuficiente en oscuro: {ratio:.2f}"

    def test_input_fondo_no_coincide_con_la_card_en_claro(self):
        """El fondo de input (hundido) debe diferenciarse de la superficie de la card."""
        G360Theme.set_theme_mode(False)
        campo = cf.text_field("X")
        assert campo.bgcolor != G360Theme.surface_color()
        assert campo.bgcolor == G360Theme.surface_sunken_color()

    def test_input_fondo_no_coincide_con_la_card_en_oscuro(self):
        G360Theme.set_theme_mode(True)
        campo = cf.text_field("X")
        assert campo.bgcolor != G360Theme.surface_color()
        assert campo.bgcolor == G360Theme.surface_sunken_color()

    def test_dropdown_y_text_field_comparten_el_mismo_fondo(self):
        """Dropdown y text_field son el mismo tipo de control: mismo bgcolor."""
        G360Theme.set_theme_mode(False)
        campo = cf.text_field("X")
        dd = cf.dropdown("Y")
        assert campo.bgcolor == dd.bgcolor

    def test_input_respeta_tema_al_crear_en_dark(self):
        """Un input creado en dark nace con el tono hundido de dark."""
        G360Theme.set_theme_mode(True)
        campo = cf.text_field("SKU")
        assert campo.bgcolor == G360Theme.SURFACE_SUNKEN
        assert campo.bgcolor == G360Theme.surface_sunken_color()

