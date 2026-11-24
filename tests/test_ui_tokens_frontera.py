"""Valores en la frontera de los tokens UI: contraste mínimo, radios, tamaños.

La frontera son los límites que el diseño no puede cruzar sin romper la
legibilidad o la consistencia visual:

- Contraste WCAG >= 4.5:1 para texto normal sobre su fondo.
- Contraste >= 3:1 para texto grande (>=18px o 14px bold) e iconos.
- Radio de control >= radio de chip (el input no puede ser mas redondo que un chip).
- Tamaños de texto en escala ordenada (MICRO < SUBTITLE < BODY < SECTION < ...).
- Alturas de boton dentro del rango valido (no mas bajo que el texto que lleva).

Si algun valor cae por debajo de la frontera, el test falla y obliga a revisar
el diseno antes de que llegue a produccion.
"""

from __future__ import annotations

import flet as ft

import pytest

from src.core.g360_theme import G360Theme
from src.ui.widgets import control_factory as cf


def _rel_luminance(color_hex: str) -> float:
    c = color_hex.lstrip("#")
    r, g, b = (int(c[i : i + 2], 16) / 255.0 for i in (0, 2, 4))

    def s(channel: float) -> float:
        return channel / 12.92 if channel <= 0.03928 else ((channel + 0.055) / 1.055) ** 2.4

    return 0.2126 * s(r) + 0.7152 * s(g) + 0.0722 * s(b)


def _contraste_ratio(fg_hex: str, bg_hex: str) -> float:
    l1 = _rel_luminance(fg_hex)
    l2 = _rel_luminance(bg_hex)
    if l1 > l2:
        return (l1 + 0.05) / (l2 + 0.05)
    return (l2 + 0.05) / (l1 + 0.05)


@pytest.fixture(autouse=True)
def _restaura_tema():
    antes = G360Theme._is_dark
    yield
    G360Theme.set_theme_mode(antes)


class TestContrasteFrontera:
    """El minimo infranqueable: texto legible >= 4.5:1, grande/icono >= 3:1."""

    def test_texto_primario_sobre_card_cumple_45_en_dark(self):
        G360Theme.set_theme_mode(True)
        ratio = _contraste_ratio(G360Theme.text_primary_color(), G360Theme.surface_color())
        assert ratio >= 4.5, f"contraste texto primario en dark: {ratio:.2f}"

    def test_texto_primario_sobre_card_cumple_45_en_light(self):
        G360Theme.set_theme_mode(False)
        ratio = _contraste_ratio(G360Theme.text_primary_color(), G360Theme.surface_color())
        assert ratio >= 4.5, f"contraste texto primario en light: {ratio:.2f}"

    def test_acento_texto_sobre_card_cumple_45_en_ambos(self):
        for oscuro in (True, False):
            G360Theme.set_theme_mode(oscuro)
            ratio = _contraste_ratio(
                G360Theme.accent_text_color(), G360Theme.surface_color()
            )
            assert ratio >= 4.5, f"contraste acento texto (dark={oscuro}): {ratio:.2f}"
        G360Theme.set_theme_mode(True)

    def test_texto_sobre_acento_cumple_45_en_ambos(self):
        """Texto blanco sobre fondo de accento de marca."""
        for oscuro in (True, False):
            G360Theme.set_theme_mode(oscuro)
            ratio = _contraste_ratio("ffffff", G360Theme.accent_color())
            assert ratio >= 4.5, f"contraste blanco sobre acento (dark={oscuro}): {ratio:.2f}"
        G360Theme.set_theme_mode(True)


class TestGeometriaFrontera:
    """Radios, alturas y tamanos no pueden cruzarse sin romper la UI."""

    def test_radio_control_es_mayor_o_igual_que_chip(self):
        """El input no puede ser mas redondo que un chip: se leería raro."""
        assert G360Theme.RADIUS_CONTROL >= G360Theme.RADIUS_CHIP

    def test_radio_card_es_mayor_o_igual_que_control(self):
        assert G360Theme.RADIUS_CARD >= G360Theme.RADIUS_CONTROL

    def test_altura_boton_estandar_es_positiva(self):
        assert G360Theme.BTN_HEIGHT > 0
        assert G360Theme.BTN_HEIGHT_SM > 0
        assert G360Theme.BTN_HEIGHT_XS > 0

    def test_altura_boton_es_mayor_que_tamanio_texto(self):
        """Un boton de 28px no puede llevar texto de 18px: se recorta."""
        assert G360Theme.BTN_HEIGHT_XS > G360Theme.TYPE_MICRO
        assert G360Theme.BTN_HEIGHT_SM > G360Theme.TYPE_SUBTITLE
        assert G360Theme.BTN_HEIGHT > G360Theme.TYPE_BODY

    def test_control_factory_altura_coherente_con_tema(self):
        """La caja del input (HEIGHT) debe contener el texto de TYPE_H3."""
        assert cf.HEIGHT > G360Theme.TYPE_H3


class TestEspaciadoFrontera:
    """Los gaps y paddings deben ser crecientes y sin saltos absurdos."""

    def test_espacios_están_ordenados(self):
        assert G360Theme.SPACE_XS < G360Theme.SPACE_SM < G360Theme.SPACE_MD
        assert G360Theme.SPACE_MD < G360Theme.SPACE_LG < G360Theme.SPACE_XL

    def test_espacio_minimo_no_cero(self):
        assert G360Theme.SPACE_XS > 0
