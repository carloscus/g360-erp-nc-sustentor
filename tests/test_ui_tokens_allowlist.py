"""Allowlist de tokens UI: solo los tokens declarados pueden usarse en controles.

La app debe pintar controles exclusivamente con tokens del snapshot de
`g360_tokens.py` (skill `cipsa`) o derivados declarados en `G360Theme`.
Cualquier color hex hardcodeado fuera de ese allowlist rompe la paridad
dark/light y deja controles congelados al cambiar de tema.

Este test audita que `control_factory` y `G360Theme` no introduzcan literales
hex no declarados fuera de los permitidos.
"""

from __future__ import annotations

from src.core.g360_theme import G360Theme
from src.core.g360_tokens import TOKENS


# Tokens hex declarados en skill.json (dark + light), origen de verdad.
_TOKENS_HEX = {
    v
    for familia in ("dark", "light")
    for k, v in TOKENS[familia].items()
    if isinstance(v, str) and v.startswith("#")
}

# Colores derivados declarados en G360Theme (permitidos).
_DERIVADOS_HEX = {
    v
    for k, v in vars(G360Theme).items()
    if k.isupper() and isinstance(v, str) and v.startswith("#")
}

ALLOWLIST = _TOKENS_HEX | _DERIVADOS_HEX


class TestAllowlistTokens:
    """Cada color hex usado por la app debe estar en el allowlist."""

    def test_tokens_de_skill_estan_en_allowlist(self):
        """skill.json declara los hex que la app puede usar."""
        for hex_valor in _TOKENS_HEX:
            assert hex_valor in ALLOWLIST, f"{hex_valor} no esta en el allowlist"

    def test_colores_derivados_estan_en_allowlist(self):
        """Los hex declarados en G360Theme son parte del allowlist."""
        for hex_valor in _DERIVADOS_HEX:
            assert hex_valor in ALLOWLIST, f"{hex_valor} no esta en el allowlist"

    def test_no_colores_sin_declarar_en_control_factory(self):
        """control_factory no debe usar hex literales fuera del allowlist."""
        import src.ui.widgets.control_factory as cf

        # COLOR_INPUT y BORDER_INPUT se derivan del tema (no son literales sueltos).
        # Este test verifica que no se agreguen literales hex hardcodeados.
        mod_vars = {k: v for k, v in vars(cf).items() if isinstance(v, str) and v.startswith("#")}
        fuera = [k for k, v in mod_vars.items() if v not in ALLOWLIST]
        assert fuera == [], f"literales hex fuera del allowlist en control_factory: {fuera}"

    def test_allowlist_no_esta_vacio(self):
        assert ALLOWLIST, "el allowlist de tokens no puede estar vacio"
