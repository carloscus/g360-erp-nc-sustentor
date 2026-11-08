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


def _df_resultado(n: int) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "SKU": [f"PRODUCTO {i:04d}" for i in range(n)],
            "CANTIDAD": [1.0] * n,
            "DIFERENCIA": [0.5] * n,
            "MONTO_NC": [0.5] * n,
        }
    )


def _texto_btn(btn) -> str:
    """Etiqueta visible de un boton flet 1.0.

    ``btn.text`` NO existe en 1.0: leerlo devuelve un atributo Python muerto
    que se crea al asignar, asi que un test que lo lea pasaria aunque el
    usuario nunca viera el cambio. Se lee el content.
    """
    return btn.content.value


class TestOrdenarTablaNoBloquea:
    """Ordenar reconstruye solo la ventana visible, no todas las filas.

    Construir un ``DataRow`` por linea cuesta ~0.8 ms: con 5.000 lineas el
    click en un header tardaba 3.7 s (medido). El resto entra por "Ver mas".
    """

    def _vista(self, filas_totales: int, filas_visibles: int):
        v = _ViewHandlers.__new__(_ViewHandlers)
        v.app = SimpleNamespace(page=None)
        v.df_historial = None
        v.tipo_actual = "DC"
        v._result_sort_col = None
        v._result_sort_asc = True
        v.chk_gen_nd = ft.Checkbox(value=False)
        v.chk_solo_ndb = ft.Checkbox(value=False)
        v.resultado = SimpleNamespace(
            resultado=SimpleNamespace(dataframe=_df_resultado(filas_totales))
        )
        v.resultados_table = ft.DataTable(columns=[], rows=[])
        for _ in range(filas_visibles):
            v.resultados_table.rows.append(ft.DataRow(cells=[]))
        # Mismo armado que view_panels: FilledButton con label en content.
        v._result_load_more_btn = ft.FilledButton(ft.Text("Ver más filas"))
        return v

    def test_ordenar_solo_reconstruye_lo_visible(self):
        v = self._vista(filas_totales=500, filas_visibles=30)

        t0 = time.perf_counter()
        v._ordenar_por("SKU")
        elapsed = time.perf_counter() - t0

        assert len(v.resultados_table.rows) == 30, "se reconstruyeron filas de mas"
        assert elapsed < 0.5, f"ordenar bloqueo {elapsed:.2f}s"
        assert _texto_btn(v._result_load_more_btn) == "Ver más (30/500)"

    def test_sin_filas_visibles_arranca_en_un_lote(self):
        """max_rows nunca queda en 0: la tabla tiene que mostrar algo."""
        v = self._vista(filas_totales=10, filas_visibles=0)

        v._ordenar_por("SKU")

        assert len(v.resultados_table.rows) == 10
        assert v._result_load_more_btn.visible is False

    def test_ordenar_conserva_el_orden_pedido(self):
        v = self._vista(filas_totales=3, filas_visibles=3)
        v.resultado.resultado.dataframe["SKU"] = ["C", "A", "B"]

        v._ordenar_por("SKU")

        # La primera celda de cada fila es el SKU: el orden es ascendente.
        def _sku_de(fila):
            celda = fila.cells[0].content
            # _cell devuelve Text o Container(Text) segun si lleva estilo.
            return celda.value if isinstance(celda, ft.Text) else celda.content.value

        assert [_sku_de(f) for f in v.resultados_table.rows] == ["A", "B", "C"]


class TestClasificarEstados:
    """El contrato de ``_clas`` vive ahora en ``_clasificar_estados``."""

    def _df(self):
        return pd.DataFrame(
            {
                "DIFERENCIA": [0.5, -0.5, 0.0, -0.5],
                "MONTO_NC": [2.0, 0.0, 0.0, 1.0],
            }
        )

    def test_contrato_genera_nd_alarma_coincide(self):
        from src.ui.resultados_view import _clasificar_estados

        assert _clasificar_estados(self._df(), marcar_nd=False) == [
            "genera",
            "alarma",
            "coincide",
            # MONTO_NC > 0 gana sobre la diferencia negativa.
            "genera",
        ]

    def test_marcar_nd_renombra_la_alarma(self):
        from src.ui.resultados_view import _clasificar_estados

        assert _clasificar_estados(self._df(), marcar_nd=True)[1] == "nd"

    def test_sin_columnas_devuelve_coincide(self):
        from src.ui.resultados_view import _clasificar_estados

        assert _clasificar_estados(pd.DataFrame({"SKU": ["A", "B"]}), marcar_nd=True) == [
            "coincide",
            "coincide",
        ]

    def test_dataframe_vacio(self):
        from src.ui.resultados_view import _clasificar_estados

        assert _clasificar_estados(pd.DataFrame(), marcar_nd=False) == []


class TestEtiquetaDeBoton:
    """flet 1.0: los botones no tienen ``text``. Asignarlo es un no-op mudo."""

    def test_set_button_text_cambia_el_label_visible(self):
        from src.ui.widgets.control_factory import set_button_text

        btn = ft.FilledButton(ft.Text("Ver más filas"))
        assert set_button_text(btn, "Ver más (30/500)") is True
        assert _texto_btn(btn) == "Ver más (30/500)"

    def test_set_button_text_recorre_un_row_con_icono(self):
        """Forma de los date-picker: Row([Icon, Text])."""
        from src.ui.widgets.control_factory import set_button_text

        btn = ft.OutlinedButton(
            content=ft.Row([ft.Icon(ft.Icons.CALENDAR_MONTH), ft.Text("Desde: Sin filtro")])
        )
        assert set_button_text(btn, "Desde: 01/10/2026") is True
        assert btn.content.controls[1].value == "Desde: 01/10/2026"

    def test_set_button_text_agrega_el_texto_si_el_row_no_tiene(self):
        from src.ui.widgets.control_factory import set_button_text

        btn = ft.OutlinedButton(content=ft.Row([ft.Icon(ft.Icons.CALENDAR_MONTH)]))
        assert set_button_text(btn, "Hasta: hoy") is True
        assert isinstance(btn.content.controls[-1], ft.Text)
        assert btn.content.controls[-1].value == "Hasta: hoy"

    def test_asignar_text_directo_no_llega_al_label(self):
        """Regresión del bug: el label se quedaba en el valor de construcción.

        Si flet alguna vez agrega ``text`` a los botones, este test falla y
        ahi se puede volver a usar la asignacion directa.
        """
        btn = ft.FilledButton(ft.Text("Ver más filas"))
        btn.text = "Ver más (1/9999)"

        assert _texto_btn(btn) == "Ver más filas", (
            "flet cambio el API de botones: revisar control_factory.set_button_text"
        )
