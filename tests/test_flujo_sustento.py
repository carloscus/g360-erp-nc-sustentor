"""El flujo de "crear sustento" no debe cortarse a mitad.

Contexto: al aplicar un fragmento como historial ("USAR COMO HISTORIAL"), el
handler llama a `_verificar_puede_ejecutar`, que refresca el botón de Ejecutar
y el hint con `control.update()`. En Flet 1.0.x, pedir `update()` de un control
que todavía no está montado lanza `RuntimeError("Control must be added to the
page first")`; 0.x lanzaba `AssertionError`.

El repo cazaba solo `AssertionError`, así que ese RuntimeError escapaba.
`safe_handler` lo tragaba sin avisar (además, no encuentra la `page` para
mostrar el snackbar) y el `page.update()` final no corría: el historial
quedaba aplicado pero el botón de Ejecutar sin refrescar.

Estos tests fijan que ambos tipos de excepción se traten como "el control
todavía no está montado" y que el flujo siga hasta repintar.
"""

from __future__ import annotations

import pytest

from src.ui.reconocimiento_view import ReconocimientoView


class _Page:
    def __init__(self):
        self.updates = 0

    def update(self):
        self.updates += 1


class _App:
    G360_SUCCESS = "OK"
    G360_WARNING = "WARN"
    G360_ERROR = "ERR"
    G360_ACCENT = "#0D2B4E"

    def __init__(self):
        self.page = _Page()

    def show_snackbar(self, *args, **kwargs):
        pass


class _ControlQueFalla:
    """Control cuyo update() lanza la excepción que lanza Flet 1.0.x."""

    def __init__(self, exc: Exception):
        self.exc = exc
        self.updates = 0
        self.value = "Datos listos"
        self.disabled = False

    def update(self):
        self.updates += 1
        raise self.exc


def _vista(exc: Exception | None = None, *, con_historial: bool = True):
    """Vista real (compone _ViewHelpers + _ViewPanels + _ViewHandlers).

    Se usa la vista completa y no un `__new__` del mixin porque
    `_verificar_puede_ejecutar` consulta `_caso_de_tipo`, que vive en
    `_ViewHelpers`.
    """
    v = ReconocimientoView(_App())
    v.build()
    v.df_historial = object() if con_historial else None
    v.tipo_actual = "DC"
    # DC exige el insumo "lista_precios"; sin él el botón queda deshabilitado
    # por diseño (no es lo que estos tests miden).
    v.lista_path = "C:\\x\\lista.xlsx"
    if exc is not None:
        v.btn_ejecutar = _ControlQueFalla(exc)
        v.lbl_ejecutar_hint = _ControlQueFalla(exc)
    return v


class TestVerificarPuedeEjecutar:
    def test_untime_error_de_flet_no_corta_el_flujo(self, tmp_db):
        """El RuntimeError real de Flet 1.0.x no debe escapar."""
        v = _vista(RuntimeError("Container(1) Control must be added to the page first"))
        antes = v.app.page.updates

        v._verificar_puede_ejecutar()  # no debe levantar

        # Y el flujo sigue: la página se repinta igual.
        assert v.app.page.updates == antes + 1

    def test_assertion_error_tampoco_corta_el_flujo(self, tmp_db):
        """El AssertionError de Flet 0.x sigue soportado."""
        v = _vista(AssertionError("control not mounted"))
        antes = v.app.page.updates

        v._verificar_puede_ejecutar()  # no debe levantar

        assert v.app.page.updates == antes + 1

    def test_sin_excepcion_repinta_normalmente(self, tmp_db):
        """El camino sano no cambió: la página repinta."""
        v = _vista()
        antes = v.app.page.updates

        v._verificar_pude_ejecutar() if False else v._verificar_puede_ejecutar()

        assert v.app.page.updates == antes + 1

    def test_el_boton_se_habilita_con_historial(self, tmp_db):
        """Con historial cargado el botón de Ejecutar queda habilitado."""
        v = _vista()

        v._verificar_pude_ejecutar() if False else v._verificar_puede_ejecutar()

        assert v.btn_ejecutar.disabled is False

    def test_el_boton_se_deshabilita_sin_historial(self, tmp_db):
        """Sin historial el botón de Ejecutar queda deshabilitado."""
        v = _vista(con_historial=False)

        v._verificar_puede_ejecutar()

        assert v.btn_ejecutar.disabled is True


@pytest.mark.parametrize(
    "exc",
    [
        RuntimeError("Container(1) Control must be added to the page first"),
        AssertionError("control not mounted"),
    ],
)
def test_safe_handler_atrapa_lo_que_se_escape(exc):
    """`safe_handler` es la red final: nada debe matar el handler."""
    from src.core.g360_theme import safe_handler

    @safe_handler
    def _boom(self, e):
        raise exc

    _boom(None, None)  # no debe levantar
