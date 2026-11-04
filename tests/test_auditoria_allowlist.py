"""Auditoría del allowlist: historial, preview y política de captura.

F1 del plan de convergencia: cada cambio de líneas queda registrado, se puede
previsualizar antes de aplicar, y la política de captura se graba para poder
explicar divergencias retroactivamente.
"""

from __future__ import annotations

from src.core import ventas_db_config as cfg


class TestAuditoriaAllowlist:
    def test_registrar_cambio_crea_fila(self, tmp_db):
        """Un cambio genera una entrada en allowlist_history."""
        cfg.registrar_cambio_allowlist(["01", "02"], ["01", "03"], motivo="prueba")
        historial = cfg.historial_allowlist()
        assert len(historial) == 1
        assert historial[0]["lines_nueva"] == ["01", "03"]
        assert historial[0]["motivo"] == "prueba"

    def test_historial_mas_reciente_primer(self, tmp_db):
        """El historial devuelve el más reciente primero."""
        cfg.registrar_cambio_allowlist(["01"], ["01", "02"], motivo="primero")
        cfg.registrar_cambio_allowlist(["01", "02"], ["01", "03"], motivo="segundo")
        historial = cfg.historial_allowlist()
        assert historial[0]["motivo"] == "segundo"
        assert historial[1]["motivo"] == "primero"

    def test_motivo_opcional(self, tmp_db):
        """Sin motivo queda vacío, no rompe."""
        cfg.registrar_cambio_allowlist(["01"], ["02"])
        historial = cfg.historial_allowlist()
        assert historial[0]["motivo"] == ""

    def test_preview_muestra_diff(self, tmp_db):
        """previsualizar_cambio no aplica, solo muestra."""
        # Setup: allowlist actual = ["01", "02"]
        cfg.save_app_config({"allowed_lines": ["01", "02"]})
        cfg.reset_allowed_lines_cache()

        preview = cfg.previsualizar_cambio(["01", "03"])
        assert preview["nuevas"] == ["03"]
        assert preview["quitadas"] == ["02"]
        assert preview["permanecen"] == ["01"]
        assert preview["total_actuales"] == 2
        assert preview["total_nuevas"] == 2

        # El allowlist real no cambió.
        assert cfg.allowed_lines() == ["01", "02"]

    def test_preview_vacio_no_rompe(self, tmp_db):
        """Preview con lista vacía no falla."""
        preview = cfg.previsualizar_cambio([])
        assert preview["nuevas"] == []
        assert preview["quitadas"] == sorted(cfg.allowed_lines())


class TestPoliticaCaptura:
    def test_grabar_y_leer(self, tmp_db):
        """La política se graba y se lee correctamente."""
        cfg.grabar_politica_captura(inmadurez=5, overlap=3, version_app="1.0.0")
        pol = cfg.politica_captura()
        assert pol["dias_inmadurez"] == "5"
        assert pol["overlap_dias"] == "3"

    def test_reemplaza_la_anterior(self, tmp_db):
        """Una nueva grabación reemplaza la anterior (INSERT OR REPLACE)."""
        cfg.grabar_politica_captura(inmadurez=3, overlap=1)
        cfg.grabar_politica_captura(inmadurez=7, overlap=5)
        pol = cfg.politica_captura()
        assert pol["dias_inmadurez"] == "7"
        assert pol["overlap_dias"] == "5"

    def test_tabla_existe_en_init_estado(self, tmp_db):
        """init_estado crea las nuevas tablas sin error."""
        conn = tmp_db.get_conn()
        tmp_db.init_estado(conn)
        # Las tablas existen.
        assert (
            bool(conn.execute("SELECT 1 FROM allowlist_history LIMIT 1").fetchone()) is False
        )  # vacía pero existe
        assert bool(conn.execute("SELECT 1 FROM capture_policy LIMIT 1").fetchone()) is False
