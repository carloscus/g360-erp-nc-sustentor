"""Tests de compatibilidad con productor Tauri (manifiesto .manifest.json)."""

import json
import sqlite3

import pytest

from src.core import ventas_db
from src.core.cartucho import _leer_manifiesto


class TestManifiestoTauri:
    def test_leer_manifest_json(self, tmp_path):
        """Acepta *.manifest.json además de CARTUCHO.json."""
        carp = tmp_path / "cartucho_tauri"
        carp.mkdir()
        man = {
            "version": 4,
            "contracto_version": "4",
            "dim_schema_version": "3",
            "normalizacion_version": "1",
            "formato": "g360-ventas-cartucho-v2",
            "espejo_completo": True,
            "sha256": "abc123",
            "rango": {"desde": "2020-01-01", "hasta": "2026-11-05"},
            "day_checksums": [],
            "cartucho_version": 1,  # compat con consumidor
        }
        (carp / "base_canonica.manifest.json").write_text(
            json.dumps(man, indent=2), encoding="utf-8"
        )
        result = _leer_manifiesto(carp)
        # La normalización convierte version → cartucho_version.
        assert result.get("cartucho_version") == 1
        assert result.get("version") == 4

    def test_ignora_cargos_legacy(self, tmp_path):
        """CARTUCHO.json tiene prioridad sobre *.manifest.json."""
        carp = tmp_path / "cartucho"
        carp.mkdir()
        (carp / "CARTUCHO.json").write_text(
            json.dumps({"version": 1, "cartucho_version": 1}), encoding="utf-8"
        )
        (carp / "base.manifest.json").write_text(
            json.dumps({"version": 4, "cartucho_version": 1}), encoding="utf-8"
        )
        result = _leer_manifiesto(carp)
        assert result["version"] == 1

    def test_error_si_no_tiene_ningun(self, tmp_path):
        """Si no hay CARTUCHO.json ni *.manifest.json, falla con error claro."""
        carp = tmp_path / "vacío"
        carp.mkdir()
        with pytest.raises(FileNotFoundError, match="CARTUCHO.json|manifest.json"):
            _leer_manifiesto(carp)

    def test_verificar_contrato_con_base_sintetica(self, tmp_path):
        """verificar_contrato pasa con una base v4 construida desde el contrato.

        Antes leia una DB real de una ruta de la maquina y saltaba si no
        existia (pytest.skip): test deshonesto y path no portable. Ahora la
        fixture se construye desde CONTRACTO_TABLAS mismo, asi el test queda
        sincronizado con el contrato y corre siempre, sin red ni archivos
        externos.
        """
        db_path = tmp_path / "base_sintetica_v4.db"
        conn = sqlite3.connect(db_path)
        try:
            # Tablas del contrato: mismas columnas, mismo orden. El schema de
            # tipos no importa para verificar_contrato (compara nombres).
            for tabla, columnas in ventas_db.CONTRACTO_TABLAS.items():
                cols_sql = ", ".join(f'"{c}" TEXT' for c in columnas)
                conn.execute(f"CREATE TABLE {tabla} ({cols_sql})")
            # Version de contrato del productor v4: en g360_meta Y en
            # PRAGMA user_version (el productor setea ambos; el campo
            # 'version' del reporte sale del PRAGMA).
            conn.execute("PRAGMA user_version = 4")
            conn.execute("CREATE TABLE g360_meta (key TEXT PRIMARY KEY, value TEXT)")
            conn.execute("INSERT INTO g360_meta (key, value) VALUES ('contracto_version', '4')")
            conn.commit()

            rep = ventas_db.verificar_contrato(conn)
            assert rep["ok"], rep["detalle"]
            assert rep["version_ok"], rep
            assert rep["version"] == 4
            assert rep["tablas_faltantes"] == [], rep["tablas_faltantes"]
            assert rep["tablas_extra_no_toleradas"] == []
        finally:
            conn.close()

    def test_verificar_contrato_rechaza_version_vieja(self, tmp_path):
        """Una base sin g360_meta y con user_version != 4 no es aceptada."""
        db_path = tmp_path / "base_vieja.db"
        conn = sqlite3.connect(db_path)
        try:
            conn.execute("PRAGMA user_version = 3")
            for tabla, columnas in ventas_db.CONTRACTO_TABLAS.items():
                cols_sql = ", ".join(f'"{c}" TEXT' for c in columnas)
                conn.execute(f"CREATE TABLE {tabla} ({cols_sql})")
            conn.commit()
            rep = ventas_db.verificar_contrato(conn)
            assert not rep["ok"]
            assert not rep["version_ok"]
        finally:
            conn.close()

    def test_normaliza_dias_y_db(self, tmp_path):
        """La normalización convierte dias (lista) y day_checksums en dict."""
        from src.core.cartucho import _normalizar_manifesto_tauri

        man_raw = {
            "version": 4,
            "espejo_completo": True,
            "sha256": "abc",
            "db_size_bytes": 1234,
            "quick_check": {"filas": 100, "soles": 500.0},
            "rango": {"desde": "2020-01-01", "hasta": "2026-11-05"},
            "dias": ["2020-01-01", "2020-01-02"],
            "day_checksums": [
                {"2020-01-01": {"filas": 10, "soles": 50.0, "checksum": "x"}},
                {"2020-01-02": {"filas": 20, "soles": 100.0, "checksum": "y"}},
            ],
        }
        man = _normalizar_manifesto_tauri(man_raw)
        assert man["cartucho_version"] == 4
        assert man["db"]["ventas_filas"] == 100
        assert man["db"]["incremental"] is False
        assert man["dias"] == {
            "2020-01-01": [10, 50.0],
            "2020-01-02": [20, 100.0],
        }
        assert "db" in man

    def test_no_toca_manifesto_consumidor(self, tmp_path):
        """Si ya tiene cartucho_version, no se modifica."""
        from src.core.cartucho import _normalizar_manifesto_tauri

        man = {"cartucho_version": 1, "db": {"archivo": "historial.db"}}
        result = _normalizar_manifesto_tauri(man)
        assert result is man
        assert result["db"]["archivo"] == "historial.db"

    def test_resolver_archivo_db_tauri(self, tmp_path):
        """Para Tauri, resuelve el nombre del archivo .db del disco."""
        from src.core.cartucho import _resolver_archivo_db

        carp = tmp_path / "cartucho"
        carp.mkdir()
        (carp / "base_canonica.db").touch()
        (carp / "other.db").touch()
        nombre = _resolver_archivo_db(carp)
        assert nombre == "base_canonica.db"

    def test_resolver_archivo_db_consumidor(self, tmp_path):
        """Para consumidor, usa db.archivo del manifiesto."""
        from src.core.cartucho import _resolver_archivo_db

        carp = tmp_path / "cartucho"
        carp.mkdir()
        man = {"db": {"archivo": "mi_db.db"}}
        assert _resolver_archivo_db(carp, man) == "mi_db.db"
