"""Paridad 1:1 de tokens UI entre roles y sus derivados.

Cada rol de color declarado por el skill (dark/light) debe tener su
contraparte derivada en `G360Theme` (surface_sunken_color, accent_color, etc.).
La paridad 1:1 garantiza que no haya un rol sin mapear ni un derivado sin
origen, que es la condición para que `apply_theme()` re-mapee todos los
controles al cambiar de tema sin dejar colores congelados.
"""

from __future__ import annotations

from src.core.g360_theme import G360Theme
from src.core.g360_tokens import TOKENS


class TestParidadRolesDerivados:
    """Cada token de skill.json debe tener su rol derivado en G360Theme."""

    def test_accent_tiene_derivado_en_ambos_temas(self):
        G360Theme.set_theme_mode(True)
        assert G360Theme.accent_color() == G360Theme.ACCENT
        G360Theme.set_theme_mode(False)
        assert G360Theme.accent_color() == G360Theme.ACCENT_LIGHT
        G360Theme.set_theme_mode(True)

    def test_text_primary_tiene_derivado_en_ambos_temas(self):
        G360Theme.set_theme_mode(True)
        assert G360Theme.text_primary_color() == G360Theme.TEXT_PRIMARY
        G360Theme.set_theme_mode(False)
        assert G360Theme.text_primary_color() == G360Theme.TEXT_PRIMARY_LIGHT
        G360Theme.set_theme_mode(True)

    def test_surface_tiene_derivado_en_ambos_temas(self):
        G360Theme.set_theme_mode(True)
        assert G360Theme.surface_color() == G360Theme.SURFACE
        G360Theme.set_theme_mode(False)
        assert G360Theme.surface_color() == G360Theme.SURFACE_LIGHT
        G360Theme.set_theme_mode(True)

    def test_accent_2_tiene_derivado_en_ambos_temas(self):
        G360Theme.set_theme_mode(True)
        assert G360Theme.accent_2_color() == G360Theme.ACCENT_2_BRIGHT
        G360Theme.set_theme_mode(False)
        assert G360Theme.accent_2_color() == G360Theme.ACCENT_2_LIGHT
        G360Theme.set_theme_mode(True)

    def test_accent_3_tiene_derivado_en_ambos_temas(self):
        G360Theme.set_theme_mode(True)
        assert G360Theme.accent_3_color() == G360Theme.ACCENT_3
        G360Theme.set_theme_mode(False)
        assert G360Theme.accent_3_color() == G360Theme.ACCENT_3_LIGHT
        G360Theme.set_theme_mode(True)

    def test_ok_color_tiene_derivado_en_ambos_temas(self):
        G360Theme.set_theme_mode(True)
        assert G360Theme.ok_color() == G360Theme.SUCCESS
        G360Theme.set_theme_mode(False)
        assert G360Theme.ok_color() == G360Theme.OK_LIGHT
        G360Theme.set_theme_mode(True)

    def test_warning_color_tiene_derivado_en_ambos_temas(self):
        G360Theme.set_theme_mode(True)
        assert G360Theme.warning_color() == G360Theme.WARNING
        G360Theme.set_theme_mode(False)
        assert G360Theme.warning_color() == G360Theme.WARNING_LIGHT
        G360Theme.set_theme_mode(True)

    def test_error_color_tiene_derivado_en_ambos_temas(self):
        G360Theme.set_theme_mode(True)
        assert G360Theme.error_color() == G360Theme.ERROR
        G360Theme.set_theme_mode(False)
        assert G360Theme.error_color() == G360Theme.ERROR_LIGHT
        G360Theme.set_theme_mode(True)


class TestParidadDarkLightValoresDistintos:
    """Dark y light no deben colapsar al mismo valor para un mismo rol."""

    def test_accent_dark_y_light_diferencian(self):
        G360Theme.set_theme_mode(True)
        d = G360Theme.accent_color()
        G360Theme.set_theme_mode(False)
        l = G360Theme.accent_color()
        G360Theme.set_theme_mode(True)
        assert d != l

    def test_text_primary_dark_y_light_diferencian(self):
        G360Theme.set_theme_mode(True)
        d = G360Theme.text_primary_color()
        G360Theme.set_theme_mode(False)
        l = G360Theme.text_primary_color()
        G360Theme.set_theme_mode(True)
        assert d != l

    def test_surface_dark_y_light_diferencian(self):
        G360Theme.set_theme_mode(True)
        d = G360Theme.surface_color()
        G360Theme.set_theme_mode(False)
        l = G360Theme.surface_color()
        G360Theme.set_theme_mode(True)
        assert d != l
