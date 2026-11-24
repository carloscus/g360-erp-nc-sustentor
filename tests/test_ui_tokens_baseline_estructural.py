"""Estructura base de los tokens UI: claves, formato y paridad dark/light.

Los tokens viven en `src/core/g360_tokens.py` (snapshot de `g360 tokens` desde
skill.json). Cada familia (dark, light) debe declarar las mismas claves, y cada
valor de color debe ser un hex válido #RRGGBB o rgba(). La paridad estructural
garantiza que `g360 tokens` no deje huérfanos al regenerar el snapshot.
"""

from __future__ import annotations

import re

import pytest

from src.core.g360_tokens import TOKENS


_HEX = re.compile(r"^#(?:[0-9a-fA-F]{3}){1,2}$")
_RGBA = re.compile(r"^rgba\(\d{1,3},\s*\d{1,3},\s*\d{1,3},\s*(?:0?\.\d+|1|0)\)$")


def _es_color_valido(valor: str) -> bool:
    return bool(_HEX.match(valor) or _RGBA.match(valor))


FAMILIAS = ("dark", "light")


class TestEstructuraTokens:
    """La forma del snapshot: mismas claves en dark y light, colores válidos."""

    def test_dark_y_light_tienen_las_mismas_claves(self):
        claves_dark = set(TOKENS["dark"])
        claves_light = set(TOKENS["light"])
        assert claves_dark == claves_light, (
            f"claves sin par: dark={sorted(claves_dark - claves_light)}, "
            f"light={sorted(claves_light - claves_dark)}"
        )

    def test_cada_clave_de_color_es_valida(self):
        """Solo las claves que son colores deben ser hex o rgba().

        blur, radius, font, fontSize, space* son medidas/texto, no colores,
        y no entran en esta validacion.
        """
        CLAVES_COLOR = {
            "bg",
            "surface",
            "surfaceAlt",
            "overlay",
            "border",
            "borderStrong",
            "text",
            "textMuted",
            "textInverse",
            "accent",
            "accentStrong",
            "accentBright",
            "accentSoft",
            "accentHover",
            "onAccent",
            "success",
            "warning",
            "error",
            "info",
            "glass",
        }
        invalidos = []
        for familia in FAMILIAS:
            for clave, valor in TOKENS[familia].items():
                if clave in CLAVES_COLOR and isinstance(valor, str):
                    if not _es_color_valido(valor):
                        invalidos.append((familia, clave, valor))
        assert invalidos == [], f"tokens de color con valor invalido: {invalidos}"

    def test_no_valores_vacios(self):
        vacios = [
            (familia, clave)
            for familia in FAMILIAS
            for clave, valor in TOKENS[familia].items()
            if not valor
        ]
        assert vacios == [], f"tokens vacios: {vacios}"

    def test_chart_tiene_dark_y_light(self):
        assert "chart" in TOKENS
        assert "dark" in TOKENS["chart"]
        assert "light" in TOKENS["chart"]
        assert len(TOKENS["chart"]["dark"]) == len(TOKENS["chart"]["light"])


class TestRolesDeclaradosPresentes:
    """Cada rol que el skill declara debe estar en el snapshot."""

    ROLES_OBLIGATORIOS = (
        "bg",
        "surface",
        "text",
        "textMuted",
        "accent",
        "success",
        "warning",
        "error",
        "info",
    )

    def test_roles_obligatorios_en_dark(self):
        for rol in self.ROLES_OBLIGATORIOS:
            assert rol in TOKENS["dark"], f"falta rol {rol} en dark"

    def test_roles_obligatorios_en_light(self):
        for rol in self.ROLES_OBLIGATORIOS:
            assert rol in TOKENS["light"], f"falta rol {rol} en light"
