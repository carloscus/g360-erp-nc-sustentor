"""Tests para la inspección liviana en update_from_last().

Cubre: omisión de hoy cuando conteo local == remoto, inclusión cuando difieren,
y fallback seguro ante fallos.
"""

from datetime import date, timedelta

from src.core import ventas_db
from src.core.capture_service import CaptureService
from src.core.intranet_client import IntranetError


class TestInspeccionLiviana:
    """Escenarios del chequeo liviano de conteo portal vs local."""

    def _sembrar_hoy(self, conn, n_filas=5):
        """Inserta n_filas con fecha de hoy en la DB."""
        hoy = date.today().isoformat()
        for i in range(n_filas):
            conn.execute(
                "INSERT INTO ventas (id_articulo, id_linea, id_cliente, tpo_doc, serie_doc, "
                "nro_doc, fecha_orig, mes_ref, cantidad, soles, anho, mes, id_vendedor, "
                "nom_vendedor, folio_unico) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    "02211",
                    "01",
                    "00004884",
                    "F01",
                    "001",
                    str(i),
                    hoy,
                    hoy[:7],
                    1.0,
                    10.0,
                    2026,
                    9,
                    "178",
                    "MILCA",
                    f"F01/001/{i}",
                ),
            )
        conn.commit()

    def test_omitir_hoy_cuando_contadores_coinciden(self, tmp_db, monkeypatch):
        """Si portal y local tienen mismo conteo para hoy → se omite hoy."""
        conn = ventas_db.get_conn()
        self._sembrar_hoy(conn, n_filas=5)
        visto_chunks = []

        def fake_capture_chunks(self, chunks):
            visto_chunks.extend(c.label for c in chunks)
            return {"filas": 0, "chunks_ok": [], "chunks_fallidos": [], "dias_fallidos": []}

        class FakeClient:
            def __init__(self, *a, **k):
                pass

            def ensure_logged_in(self):
                pass

            def close(self):
                pass

            def count_grid_rows(self, desde, hasta):
                # Portal reporta mismo conteo que local: 5
                return 5

        # Parchear IntranetClient completo (en el módulo donde se importa)
        monkeypatch.setattr("src.core.intranet_client.IntranetClient", FakeClient)
        # También parchear _progress para evitar logs
        monkeypatch.setattr(CaptureService, "_progress", lambda self, *a, **k: None)
        monkeypatch.setattr(CaptureService, "capture_chunks", fake_capture_chunks)
        monkeypatch.setenv("G360_INTRANET_USER", "usr")
        monkeypatch.setenv("G360_INTRANET_PASS", "pwd")

        svc = CaptureService()
        svc.update_from_last()

        # Hoy NO debe estar en los chunks planificados
        hoy_iso = date.today().isoformat()
        assert hoy_iso not in visto_chunks

    def test_incluir_hoy_cuando_contadores_difieren(self, tmp_db, monkeypatch):
        """Si portal tiene más filas que local → se incluye hoy."""
        conn = ventas_db.get_conn()
        self._sembrar_hoy(conn, n_filas=5)
        visto_chunks = []

        def fake_capture_chunks(self, chunks):
            visto_chunks.extend(c.label for c in chunks)
            return {"filas": 0, "chunks_ok": [], "chunks_fallidos": [], "dias_fallidos": []}

        class FakeClient:
            def __init__(self, *a, **k):
                pass

            def ensure_logged_in(self):
                pass

            def close(self):
                pass

            def count_grid_rows(self, desde, hasta):
                # Portal reporta 8, local tiene 5 → hay diferencias
                return 8

        monkeypatch.setattr("src.core.intranet_client.IntranetClient", FakeClient)
        monkeypatch.setattr(CaptureService, "capture_chunks", fake_capture_chunks)
        monkeypatch.setenv("G360_INTRANET_USER", "usr")
        monkeypatch.setenv("G360_INTRANET_PASS", "pwd")

        svc = CaptureService()
        svc.update_from_last()

        hoy_iso = date.today().isoformat()
        assert hoy_iso in visto_chunks

    def test_fallback_incluye_hoy_si_portal_falla(self, tmp_db, monkeypatch):
        """Si la sonda al portal falla → se incluye hoy por seguridad."""
        conn = ventas_db.get_conn()
        self._sembrar_hoy(conn, n_filas=5)
        visto_chunks = []

        def fake_capture_chunks(self, chunks):
            visto_chunks.extend(c.label for c in chunks)
            return {"filas": 0, "chunks_ok": [], "chunks_fallidos": [], "dias_fallidos": []}

        class FakeClient:
            def __init__(self, *a, **k):
                pass

            def ensure_logged_in(self):
                pass

            def close(self):
                pass

            def count_grid_rows(self, desde, hasta):
                raise IntranetError("error de red simulado")

        monkeypatch.setattr("src.core.intranet_client.IntranetClient", FakeClient)
        monkeypatch.setattr(CaptureService, "capture_chunks", fake_capture_chunks)
        monkeypatch.setenv("G360_INTRANET_USER", "usr")
        monkeypatch.setenv("G360_INTRANET_PASS", "pwd")

        svc = CaptureService()
        svc.update_from_last()

        # Ante fallo, hoy DEBE incluirse
        hoy_iso = date.today().isoformat()
        assert hoy_iso in visto_chunks

    def test_sin_credenciales_no_hace_omon(self, tmp_db, monkeypatch):
        """Sin credenciales → no intenta inspección, incluye hoy por defecto."""
        conn = ventas_db.get_conn()
        self._sembrar_hoy(conn, n_filas=5)
        visto_chunks = []

        def fake_capture_chunks(self, chunks):
            visto_chunks.extend(c.label for c in chunks)
            return {"filas": 0, "chunks_ok": [], "chunks_fallidos": [], "dias_fallidos": []}

        monkeypatch.setattr(CaptureService, "capture_chunks", fake_capture_chunks)
        # Sin credenciales
        monkeypatch.delenv("G360_INTRANET_USER", raising=False)
        monkeypatch.delenv("G360_INTRANET_PASS", raising=False)

        svc = CaptureService()
        svc.update_from_last()

        hoy_iso = date.today().isoformat()
        assert hoy_iso in visto_chunks

    def test_no_aplica_cuando_fmax_diferente_a_hoy(self, tmp_db, monkeypatch):
        """Inspección liviana solo cuando fmax == hoy; si hay brecha, ignora."""
        conn = ventas_db.get_conn()
        # Sembrar con fecha antigua, no hoy
        ant = (date.today() - timedelta(days=10)).isoformat()
        conn.execute(
            "INSERT INTO ventas (id_articulo, id_linea, id_cliente, tpo_doc, serie_doc, "
            "nro_doc, fecha_orig, mes_ref, cantidad, soles, anho, mes, id_vendedor, "
            "nom_vendedor, folio_unico) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                "02211",
                "01",
                "00004884",
                "F01",
                "001",
                "1",
                ant,
                ant[:7],
                1.0,
                10.0,
                2026,
                9,
                "178",
                "MILCA",
                "F01/001/1",
            ),
        )
        conn.commit()
        visto_chunks = []

        def fake_capture_chunks(self, chunks):
            visto_chunks.extend(c.label for c in chunks)
            return {"filas": 0, "chunks_ok": [], "chunks_fallidos": [], "dias_fallidos": []}

        class FakeClient:
            def __init__(self, *a, **k):
                pass

            def ensure_logged_in(self):
                pass

            def close(self):
                pass

            def count_grid_rows(self, desde, hasta):
                return 0

        monkeypatch.setattr("src.core.intranet_client.IntranetClient", FakeClient)
        monkeypatch.setattr(CaptureService, "capture_chunks", fake_capture_chunks)
        monkeypatch.setenv("G360_INTRANET_USER", "usr")
        monkeypatch.setenv("G360_INTRANET_PASS", "pwd")

        svc = CaptureService()
        svc.update_from_last()

        # Con brecha grande, debe planificar meses, no solo hoy
        # La inspección liviana no aplica porque fmax != hoy
        assert len(visto_chunks) > 0  # algo se planificó
