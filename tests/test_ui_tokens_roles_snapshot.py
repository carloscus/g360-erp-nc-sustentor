"""Snapshot de roles de tokens: cada rol hex tiene contraparte en _color_map.

El `_color_map` de `G360Theme` mapea valores hex (fondo de controles ya
construidos, literales congelados) al tono del tema actual. Si un token hex
declarante no entra al mapa, `apply_theme` no puede re-mapearlo y el control
se queda con el color del tema anterior (fondo oscuro en tema claro).
Este test hace de guardia contra ese olvido.
"""

from __future__ import annotations

from src.core.g360_theme import G360Theme


class TestRolesSnapshot:
    """Cada token de color hex declarante debe estar en el mapa de re-mapeo."""

    FUERA_DE_ALCANCE = {
        "BG_DARK",
        "BG_LIGHT",
        "ACCENT_4",
        "FONT_FAMILY",
        "FONT_FAMILY_MONO",
        "BORDER",
        "BORDER_SUBTLE",
        "TEXT_SECONDARY",
        "SHADOW_COLOR",
        "SPACE_XS",
        "SPACE_SM",
        "SPACE_MD",
        "SPACE_LG",
        "SPACE_XL",
        "RADIUS_CHIP",
        "RADIUS_CONTROL",
        "RADIUS_CARD",
        "RADIUS_PILL",
        "TYPE_KPI",
        "TYPE_DISPLAY",
        "TYPE_H2",
        "TYPE_H3",
        "TYPE_TITLE",
        "TYPE_SECTION",
        "TYPE_BODY",
        "TYPE_SUBTITLE",
        "TYPE_SMALL",
        "TYPE_MICRO",
        "BTN_HEIGHT",
        "BTN_HEIGHT_SM",
        "BTN_HEIGHT_XS",
        "CARD_RADIUS",
        "BTN_RADIUS",
    }

    def test_ningun_token_hex_declarante_queda_fuera_del_mapa(self):
        """Guard contra el forgotismo: cada token hex tiene contraparte."""
        mapa = G360Theme._color_map()
        huerfanos = []
        for nombre in dir(G360Theme):
            if not nombre.isupper() or nombre in self.FUERA_DE_ALCANCE:
                continue
            valor = getattr(G360Theme, nombre)
            if isinstance(valor, str) and valor.startswith("#") and valor not in mapa:
                huerfanos.append(nombre)
        assert huerfanos == [], f"tokens sin mapear: {huerfanos}"

    def test_mapa_cubre_todos_los_colores_de_skill(self):
        """Los valores hex de skill.json (dark y light) deben estar en el mapa."""
        # ACCENT dark y su derivado light
        assert G360Theme.ACCENT in G360Theme._color_map()
        assert G360Theme.ACCENT_LIGHT in G360Theme._color_map()
        # TEXT_PRIMARY dark y light
        assert G360Theme.TEXT_PRIMARY in G360Theme._color_map()
        assert G360Theme.TEXT_PRIMARY_LIGHT in G360Theme._color_map()
        # SURFACE dark y light
        assert G360Theme.SURFACE in G360Theme._color_map()
        assert G360Theme.SURFACE_LIGHT in G360Theme._color_map()

    def test_valores_no_hex_no_estan_en_mapa(self):
        """Los tokens que no son strings hex (font, space, radius) no entran."""
        mapa = G360Theme._color_map()
        for nombre in ("FONT_FAMILY", "SPACE_MD", "RADIUS_CONTROL"):
            valor = getattr(G360Theme, nombre)
            assert valor not in mapa.values() or not isinstance(valor, str)

    def test_mapa_no_tiene_duplicados_de_origen(self):
        """Cada valor de origen hex mapea a un solo destino por modo."""
        mapa = G360Theme._color_map()
        orígenes = list(mapa.keys())
        assert len(orígenes) == len(set(orígenes)), "claves duplicadas en _color_map"
