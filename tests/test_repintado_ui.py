"""Contrato de repintado: los controles que recalculan deben mandar el frame.

En flet 1.0 desktop un cambio de estado sin ``page.update()`` no se ve hasta el
proximo evento del sistema (cambio de foco): el control parece "pensando".
Estos tests fijan el contrato minimo para los casos que lo rompian, y para el
arranque: la card DB se refresca en background para no retrasar el primer frame.
"""

import threading
import time
from types import SimpleNamespace

import flet as ft
import pandas as pd

from src.ui.reporte_panel import ReportePanel
from src.ui.view_handlers import _ViewHandlers
from src.ui.view_panels import _ViewPanels


class _Page:
    def __init__(self):
        self.updates = 0

    def update(self):
        self.updates += 1


class _FakeApp:
    G360_ACCENT = "#0D2B4E"
    G360_SUCCESS = "OK"
    G360_WARNING = "WARN"
    G360_ERROR = "ERR"

    def __init__(self):
        self.page = _Page()

    def show_snackbar(self, msg, color=None):
        pass


class TestToggleNcReporte:
    def test_checkbox_tiene_handler_y_repinta(self):
        app = _FakeApp()
        panel = ReportePanel(app, SimpleNamespace())
        panel.construir_card()

        assert panel.nc_sw.on_change is not None, "sin on_change no hay frame inmediato"
        antes = app.page.updates
        panel.nc_sw.value = not panel.nc_sw.value
        panel._on_nc_toggle(SimpleNamespace(control=panel.nc_sw))
        assert app.page.updates == antes + 1

    def test_toggle_no_recalcula_datos(self):
        """El handler solo repinta: el valor se lee al pulsar Ver datos."""
        app = _FakeApp()
        panel = ReportePanel(app, SimpleNamespace())
        panel.construir_card()
        antes = dict(panel.state)
        panel._on_nc_toggle(SimpleNamespace(control=panel.nc_sw))
        assert panel.state == antes


class TestOpcionesCalculo:
    def _obj(self, df):
        return SimpleNamespace(
            app=SimpleNamespace(page=_Page()),
            resultado=SimpleNamespace(resultado=SimpleNamespace(dataframe=df)),
            _mostrar_resultado=lambda: None,
        )

    def test_un_cliente_repinta(self):
        obj = self._obj(pd.DataFrame({"a": [1, 2]}))
        _ViewHandlers._on_opciones_calculo_change(obj, None)
        assert obj.app.page.updates == 1

    def test_sin_resultado_no_repinta(self):
        obj = SimpleNamespace(
            app=SimpleNamespace(page=_Page()),
            resultado=None,
            _mostrar_resultado=lambda: None,
        )
        _ViewHandlers._on_opciones_calculo_change(obj, None)
        assert obj.app.page.updates == 0

    def test_dataframe_vacio_no_repinta(self):
        obj = self._obj(pd.DataFrame({"a": []}))
        _ViewHandlers._on_opciones_calculo_change(obj, None)
        assert obj.app.page.updates == 0


class TestArranqueNoBloquea:
    """El primer frame no espera al escaneo de la DB (~2.8M filas)."""

    def _vista(self):
        v = _ViewPanels.__new__(_ViewPanels)
        v.app = SimpleNamespace(page=None)
        v.card_db_kpis = ft.Column()
        v.card_db_status = ft.Text("Calculando…")
        v.card_db_alerta = ft.Text("")
        v.btn_ver_detalle = ft.TextButton()
        v.btn_config = ft.IconButton()
        v.btn_actualizar_hoy = ft.TextButton()
        v._db_detalle_visible = False
        return v

    def test_refrescar_card_db_async_retorna_sin_esperar(self, monkeypatch):
        from src.ui import view_panels

        v = self._vista()
        arrancado = threading.Event()
        liberar = threading.Event()

        def lento():
            arrancado.set()
            liberar.wait(5)
            return {"exists": False}

        monkeypatch.setattr(view_panels.ventas_db, "db_card_info", lento)
        t0 = time.perf_counter()
        v._refrescar_card_db(async_=True)
        elapsed = time.perf_counter() - t0

        assert elapsed < 0.5, f"async_=True bloqueo {elapsed:.2f}s"
        assert arrancado.wait(2.0), "el worker nunca arranco"
        liberar.set()

    def test_build_pide_el_refresh_en_background(self, monkeypatch):
        """build() no puede escanear la DB en el hilo de UI."""
        from src.ui.reconocimiento_view import ReconocimientoView

        v = ReconocimientoView.__new__(ReconocimientoView)
        v.app = SimpleNamespace(page=None)
        monkeypatch.setattr(ReconocimientoView, "_init_controls", lambda self: None)
        monkeypatch.setattr(ReconocimientoView, "_renderizar_ui", lambda self: None)
        monkeypatch.setattr(ReconocimientoView, "_iniciar_poll_captura", lambda self: None)
        capturado = {}
        monkeypatch.setattr(
            ReconocimientoView,
            "_refrescar_card_db",
            lambda self, async_=False: capturado.update(async_=async_),
        )

        v.build()

        assert capturado == {"async_": True}
