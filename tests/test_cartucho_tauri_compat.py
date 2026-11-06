"""Tests de compatibilidad con productor Tauri (manifiesto .manifest.json)."""

import json
import sqlite3
import tempfile
from pathlib import Path

import pytest

from src.core import ventas_db
from src.core.cartucho import _leer_manifiesto, importar_cartucho


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
        assert result["version"] == 4

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
