"""Fixture doradas: convergencia entre repos sin red.

El problema que resuelven: dos clientes (o el Tauri y el sustentor) capturan
el mismo día del mismo ERP y deben producir las mismas filas normalizadas. Sin
esta prueba, el drift pasa desapercibido hasta que un reporte no cuadra.

Cada fixture es un JSON con `input` (filas tal como salen del ERP, con dd/mm/yyyy,
espacios en id_pedido, etc.) y `expected` (filas después de pasar por la cadena
de normalización de ese repo).

Si un repo falla, la convergencia está rota — y se detecta en CI antes de
llegar a producción.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.core import ventas_db

HERE = Path(__file__).parent
FIXTURES_DIR = HERE / "fixtures_doradas"


def _load(name: str) -> dict:
    path = FIXTURES_DIR / f"{name}.json"
    if not path.exists():
        pytest.skip(f"fixture {name} no existe en {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _aplicar_normalizacion(fila: dict) -> dict:
    """Simula el paso por `_preparar_fila` + normalización de copias."""
    # `_preparar_fila` trabaja sobre dicts; `normaliza_id_pedido_fila` sobre tuples.
    # Usamos _preparar_fila que cubre fechas + id_pedido + mes_ref.
    return ventas_db._preparar_fila(fila)


class TestFixtureDoradas:
    """Tests de convergencia: input crudo del ERP → salida normalizada esperada."""

    def test_fixture_existe(self):
        """El directorio de fixtures debe existir."""
        assert FIXTURES_DIR.exists(), (
            f"{FIXTURES_DIR} no existe. Crear tests/fixtures_doradas/ y "
            "popular con .json de input/expected."
        )

    def test_fechas_crudas_se_normalizan(self, tmp_db, sample_ventas):
        """Fecha en dd/mm/yyyy del ERP → ISO en la salida."""
        data = _load("fechas_crudas")
        entrada = data["input"]
        esperado = data["expected"]

        assert len(entrada) == len(esperado), (
            f"fechas_crudas: entrada ({len(entrada)}) != expected ({len(esperado)})"
        )

        for i, (inp, exp) in enumerate(zip(entrada, esperado)):
            fila = _aplicar_normalizacion(inp)
            assert fila["fecha_orig"] == exp["fecha_orig"], (
                f"fila {i}: fecha_orig esperada {exp['fecha_orig']!r}, "
                f"obtenida {fila['fecha_orig']!r}"
            )
            if "fec_cargo" in exp:
                assert fila.get("fec_cargo") == exp["fec_cargo"], (
                    f"fila {i}: fec_cargo esperada {exp['fec_cargo']!r}, "
                    f"obtenida {fila.get('fec_cargo')!r}"
                )

    def test_id_pedido_con_espacios_se_normaliza(self, tmp_db, sample_ventas):
        """id_pedido con espacios del ERP → guion bajo en la salida."""
        data = _load("id_pedido_espacios")
        entrada = data["input"]
        esperado = data["expected"]

        assert len(entrada) == len(esperado)

        for i, (inp, exp) in enumerate(zip(entrada, esperado)):
            fila = _aplicar_normalizacion(inp)
            assert fila["id_pedido"] == exp["id_pedido"], (
                f"fila {i}: id_pedido esperada {exp['id_pedido']!r}, obtenida {fila['id_pedido']!r}"
            )

    def test_mes_ref_se_deriva_de_fecha_orig(self, tmp_db, sample_ventas):
        """mes_ref se deriva de fecha_orig, no se copia."""
        data = _load("mes_ref_derivado")
        entrada = data["input"]
        esperado = data["expected"]

        assert len(entrada) == len(esperado)

        for i, (inp, exp) in enumerate(zip(entrada, esperado)):
            fila = _aplicar_normalizacion(inp)
            assert fila["mes_ref"] == exp["mes_ref"], (
                f"fila {i}: mes_ref esperada {exp['mes_ref']!r}, obtenida {fila['mes_ref']!r}"
            )

    def test_no_se_pierden_filas(self):
        """El número de filas de entrada debe igualar al de salida."""
        for nombre in ("fechas_crudas", "id_pedido_espacios", "mes_ref_derivado"):
            try:
                data = _load(nombre)
                assert len(data["input"]) == len(data["expected"]), (
                    f"{nombre}: entrada ({len(data['input'])}) != expected "
                    f"({len(data['expected'])})"
                )
            except pytest.skip.Exception:
                pass

    def test_expected_pasa_contrato(self):
        """Las filas esperadas deben tener formato ISO y ser consistentes."""
        for nombre in ("fechas_crudas", "id_pedido_espacios", "mes_ref_derivado"):
            try:
                data = _load(nombre)
            except pytest.skip.Exception:
                continue
            for fila in data["expected"]:
                if "fecha_orig" in fila and fila["fecha_orig"]:
                    fech = str(fila["fecha_orig"])
                    assert len(fech) >= 10 and fech[4] == "-" and fech[7] == "-", (
                        f"fecha_orig debe ser ISO: {fech!r}"
                    )
                if "id_pedido" in fila and fila["id_pedido"]:
                    ped = str(fila["id_pedido"])
                    assert " " not in ped, f"id_pedido no debe tener espacios: {ped!r}"


class TestEjemploConcreto:
    """Caso real derivado de la base: un documento con todo sucio."""

    def test_documento_completo_sucio_se_normaliza(self, tmp_db, sample_ventas):
        """Simula un documento que llega del ERP con formatos crudos."""
        conn = tmp_db.get_conn()

        # Fila sucia: fechas en dd/mm/yyyy, id_pedido con espacios.
        fila_sucia = dict(
            sample_ventas[0],
            fecha_orig="15/01/2024",
            fecha_ref="14/01/2024",
            fec_cargo="14/01/2024",
            id_pedido="SADIE  25  X",
            folio_unico="DOC-SUCIO-001",
        )

        ventas_db.insert_ventas(conn, [fila_sucia], label="2024-01-15")

        # Verificar normalización.
        row = conn.execute(
            "SELECT fecha_orig, fecha_ref, fec_cargo, id_pedido, mes_ref "
            "FROM ventas WHERE folio_unico = ?",
            ("DOC-SUCIO-001",),
        ).fetchone()

        assert row[0] == "2024-01-15", f"fecha_orig no ISO: {row[0]!r}"
        assert row[1] == "2024-01-14", f"fecha_ref no ISO: {row[1]!r}"
        assert row[2] == "2024-01-14", f"fec_cargo no ISO: {row[2]!r}"
        assert row[3] == "SADIE_25_X", f"id_pedido no normalizado: {row[3]!r}"
        assert row[4] == "2024-01", f"mes_ref incorrecto: {row[4]!r}"
