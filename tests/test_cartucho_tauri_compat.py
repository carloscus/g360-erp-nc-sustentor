"""Tests de compatibilidad con productor Tauri (manifiesto .manifest.json)."""

import json
import sqlite3
from pathlib import Path

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

    def test_verificar_contrato_con_base_real(self, tmp_path):
        """Verificar_contrato pasa con la base del productor (v4)."""
        db_src = Path(
            r"C:\Users\ccusi\AppData\Local\Temp\opencode\cartucho_check\base_canonica_20261106_143935.db"
        )
        if not db_src.exists():
            pytest.skip("base de prueba no disponible")
        conn = sqlite3.connect(f"file:{db_src.as_posix()}?mode=ro", uri=True)
        try:
            rep = ventas_db.verificar_contrato(conn)
            assert rep["ok"], rep["detalle"]
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
