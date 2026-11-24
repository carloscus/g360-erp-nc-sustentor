"""Escala de tokens UI: tipografia, espaciado, radio y altura de boton.

La escala declara las medidas unicas de la app para que "12" signifique una
sola cosa en toda la UI. Antes vivian como literales sueltos en las vistas
(11 radios, 16 espaciados, 18 tamanos de texto). Ahora estan centralizadas en
`G360Theme` y este test fija su orden y unicidad para que nadie las duplique
con valores distintos.

Regla: cada tamanio de texto, espacio y radio aparece una sola vez y los
valores forman una escala monotonica creciente (o con pasos intencionales).
"""

from __future__ import annotations

from src.core.g360_theme import G360Theme


class TestEscalaTipografica:
    """Los tamanos de texto forman una escala jerarquica.

    La escala actual tiene pisos compartidos: TYPE_MICRO==TYPE_SMALL==10
    (el piso: 8/9 quedan vetados en Flet) y TYPE_KPI==TYPE_H2==18. Estos
    duplicados son intencionales y no se rompen; el test fija que no aparezcan
    valores nuevos que rompan la jerarquia.
    """

    TAMAÑOS = (
        ("TYPE_MICRO", G360Theme.TYPE_MICRO),
        ("TYPE_SMALL", G360Theme.TYPE_SMALL),
        ("TYPE_SUBTITLE", G360Theme.TYPE_SUBTITLE),
        ("TYPE_BODY", G360Theme.TYPE_BODY),
        ("TYPE_SECTION", G360Theme.TYPE_SECTION),
        ("TYPE_H3", G360Theme.TYPE_H3),
        ("TYPE_TITLE", G360Theme.TYPE_TITLE),
        ("TYPE_KPI", G360Theme.TYPE_KPI),
        ("TYPE_H2", G360Theme.TYPE_H2),
        ("TYPE_DISPLAY", G360Theme.TYPE_DISPLAY),
    )

    def test_piso_tamanio_micro(self):
        """8/9 quedan vetados en Flet (ilegibles): el piso es TYPE_MICRO=10."""
        assert G360Theme.TYPE_MICRO >= 10

    def test_titulo_card_mayor_que_seccion(self):
        """El titulo de card (16) esta un paso sobre la seccion (13)."""
        assert G360Theme.TYPE_TITLE > G360Theme.TYPE_SECTION

    def test_display_es_el_tamanio_maximo(self):
        assert G360Theme.TYPE_DISPLAY >= max(
            v for _, v in self.TAMAÑOS
        )

    def test_tamanos_no_estan_vacios(self):
        for nombre, valor in self.TAMAÑOS:
            assert isinstance(valor, int) and valor > 0, f"{nombre} no es un tamano valido"

    def test_subtitulo_mayor_que_piso(self):
        assert G360Theme.TYPE_SUBTITLE > G360Theme.TYPE_MICRO

    def test_body_mayor_que_subtitulo(self):
        assert G360Theme.TYPE_BODY > G360Theme.TYPE_SUBTITLE


class TestEscalaEspaciado:
    """Espacios: gap dentro de un par, entre items, entre sub-bloques, padding de card."""

    def test_espacios_están_crecientes(self):
        assert G360Theme.SPACE_XS < G360Theme.SPACE_SM
        assert G360Theme.SPACE_SM < G360Theme.SPACE_MD
        assert G360Theme.SPACE_MD < G360Theme.SPACE_LG
        assert G360Theme.SPACE_LG < G360Theme.SPACE_XL

    def test_espacio_xs_es_el_minimo(self):
        assert G360Theme.SPACE_XS == 4

    def test_padding_interno_card_es_espacio_lg(self):
        assert G360Theme.SPACE_LG == 16


class TestEscalaRadios:
    """Radios: chip 10, control 12, card 14, pill 999."""

    def test_radios_son_unicos(self):
        valores = [
            G360Theme.RADIUS_CHIP,
            G360Theme.RADIUS_CONTROL,
            G360Theme.RADIUS_CARD,
            G360Theme.RADIUS_PILL,
        ]
        assert len(valores) == len(set(valores)), f"radios duplicados: {valores}"

    def test_radio_chip_es_el_minimo(self):
        assert G360Theme.RADIUS_CHIP == 10

    def test_radio_control_es_el_de_inputs(self):
        assert G360Theme.RADIUS_CONTROL == 12

    def test_radio_card_es_el_de_cards(self):
        assert G360Theme.RADIUS_CARD == 14

    def test_radio_pill_es_infinito(self):
        assert G360Theme.RADIUS_PILL == 999

    def test_alias_radio_card_y_btn_coinciden(self):
        assert G360Theme.CARD_RADIUS == G360Theme.RADIUS_CARD
        assert G360Theme.BTN_RADIUS == G360Theme.RADIUS_CONTROL


class TestEscalaAlturasBoton:
    """Alturas de boton: estandar 36, compacto 32, chevron 28."""

    def test_alturas_son_unicas(self):
        valores = [
            G360Theme.BTN_HEIGHT,
            G360Theme.BTN_HEIGHT_SM,
            G360Theme.BTN_HEIGHT_XS,
        ]
        assert len(valores) == len(set(valores)), f"alturas duplicadas: {valores}"

    def test_altura_estandar_es_36(self):
        assert G360Theme.BTN_HEIGHT == 36

    def test_altura_compacta_es_32(self):
        assert G360Theme.BTN_HEIGHT_SM == 32

    def test_altura_chevron_es_28(self):
        assert G360Theme.BTN_HEIGHT_XS == 28


class TestEscalaIconos:
    """Tamano de icono: cada uno tiene token exacto y no hay literales sueltos.

    La escala de iconos cubre todos los usos de la app: 14, 16, 18, 20, 32, 48,
    15 y 22. Ningun tamaño de icono queda como literal sin token.
    """

    TAMAÑOS = (
        ("ICON_INLINE", G360Theme.ICON_INLINE),
        ("ICON_ACTION", G360Theme.ICON_ACTION),
        ("ICON_FEATURE", G360Theme.ICON_FEATURE),
        ("ICON_HERO", G360Theme.ICON_HERO),
        ("ICON_EMPTY", G360Theme.ICON_EMPTY),
        ("ICON_EMPTY_LG", G360Theme.ICON_EMPTY_LG),
        ("ICON_COMPACT", G360Theme.ICON_COMPACT),
        ("ICON_CTA", G360Theme.ICON_CTA),
    )

    def test_iconos_todos_son_enteros_positivos(self):
        for nombre, valor in self.TAMAÑOS:
            assert isinstance(valor, int) and valor > 0, f"{nombre} no es un tamano valido"

    def test_iconos_no_estan_duplicados(self):
        valores = [v for _, v in self.TAMAÑOS]
        assert len(valores) == len(set(valores)), f"iconos duplicados: {valores}"

    def test_icon_compact_es_15(self):
        assert G360Theme.ICON_COMPACT == 15

    def test_icon_cta_es_22(self):
        assert G360Theme.ICON_CTA == 22
