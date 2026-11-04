"""idx_venta_cliente_fecha: el compuesto que evita leer la historia del cliente.

Sin el, todo fetch por cliente con rango de fechas usa un indice que solo tiene
id_cliente y descarta por fecha DESPUES de leer todas las filas del cliente.
"""

import sqlite3
import sys

from src.core import agregar_indice_cliente_fecha as script
from src.core import ventas_db

SQL_COMPRAS = script.SQL_MEDICION


def _plan(conn: sqlite3.Connection, cliente="C007") -> str:
    filas = conn.execute(
        "EXPLAIN QUERY PLAN " + SQL_COMPRAS, (cliente, "2024-03-01", "2024-03-31")
    ).fetchall()
    return " | ".join(r[3] for r in filas)


def _db_sintetica(ruta, con_indice: bool) -> sqlite3.Connection:
    """40 clientes x 24 meses x 30 filas: el planner ya tiene de donde elegir."""
    conn = sqlite3.connect(ruta)
    conn.execute(
        "CREATE TABLE ventas(id_cliente TEXT, fecha_orig TEXT, mes_ref TEXT,"
        " soles REAL, tpo_doc TEXT, serie_doc TEXT, nro_doc TEXT)"
    )
    filas = []
    for c in range(40):
        for m in range(1, 25):
            mes = f"2024-{m:02d}" if m <= 12 else f"2025-{m - 12:02d}"
            for k in range(30):
                filas.append(
                    (
                        f"C{c:03d}",
                        f"{mes}-{k % 28 + 1:02d}",
                        mes,
                        10.0,
                        "FAC",
                        "F01",
                        f"{k}",
                    )
                )
    conn.executemany("INSERT INTO ventas VALUES (?,?,?,?,?,?,?)", filas)
    conn.execute("CREATE INDEX idx_venta_cliente ON ventas(id_cliente)")
    conn.execute("CREATE INDEX idx_venta_mes ON ventas(mes_ref)")
    if con_indice:
        conn.execute(script.DDL)
    conn.commit()
    return conn


class TestDeclaracion:
    def test_esta_en_create_indexes(self):
        assert "ON ventas(id_cliente, fecha_orig)" in " ".join(ventas_db.CREATE_INDEXES)

    def test_init_db_lo_crea(self, tmp_db):
        conn = tmp_db.get_conn()
        nombres = {
            r[0]
            for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'index' AND tbl_name = 'ventas'"
            ).fetchall()
        }
        assert "idx_venta_cliente_fecha" in nombres


class TestPlan:
    def test_sin_el_indice_lee_la_historia_completa(self, tmp_path):
        conn = _db_sintetica(tmp_path / "sin.db", con_indice=False)
        try:
            plan = _plan(conn)
            assert "idx_venta_cliente_fecha" not in plan
            assert "idx_venta_cliente" in plan
            # La fecha no entra en la busqueda: se descarta fila por fila.
            assert "fecha_orig" not in plan
        finally:
            conn.close()

    def test_con_el_indice_busca_por_cliente_y_fecha(self, tmp_path):
        # Ojo: "con.db" es un nombre de dispositivo reservado en Windows.
        conn = _db_sintetica(tmp_path / "con_indice.db", con_indice=True)
        try:
            plan = _plan(conn)
            assert "idx_venta_cliente_fecha" in plan
            assert "fecha_orig" in plan
        finally:
            conn.close()

    def test_devuelve_solo_el_rango(self, tmp_path):
        conn = _db_sintetica(tmp_path / "rango.db", con_indice=True)
        try:
            filas = conn.execute(SQL_COMPRAS, ("C007", "2024-03-01", "2024-03-31")).fetchall()
            assert [f[0] for f in filas] == ["2024-03"]
            assert filas[0][2] == 30
        finally:
            conn.close()


class TestScript:
    def test_sin_aplicar_no_escribe_y_con_aplicar_es_idempotente(
        self, populated_db, monkeypatch, capsys
    ):
        ruta = populated_db.db_path()
        conn = populated_db.get_conn()
        conn.execute("DROP INDEX IF EXISTS idx_venta_cliente_fecha")
        conn.commit()
        assert "idx_venta_cliente_fecha" not in _nombres_indices(conn)

        monkeypatch.setattr(sys, "argv", ["x", "--db", str(ruta)])
        assert script.main() == 0
        assert "solo informe" in capsys.readouterr().out
        assert "idx_venta_cliente_fecha" not in _nombres_indices(conn)

        monkeypatch.setattr(sys, "argv", ["x", "--db", str(ruta), "--aplicar"])
        assert script.main() == 0
        assert "idx_venta_cliente_fecha" in _nombres_indices(conn)

        assert script.main() == 0
        salida = capsys.readouterr().out
        assert "ya existe" in salida
        assert "idx_venta_cliente_fecha" in _nombres_indices(conn)

    def test_db_vacia_informa_y_no_crea(self, tmp_db, monkeypatch, capsys):
        ruta = tmp_db.db_path()
        conn = tmp_db.get_conn()
        conn.execute("DROP INDEX IF EXISTS idx_venta_cliente_fecha")
        conn.commit()

        monkeypatch.setattr(sys, "argv", ["x", "--db", str(ruta), "--aplicar"])
        assert script.main() == 0
        assert "vacia" in capsys.readouterr().out
        assert "idx_venta_cliente_fecha" not in _nombres_indices(conn)

    def test_sin_mes_ref_usa_fecha_orig(self, tmp_path, monkeypatch, capsys):
        """Bases viejas sin `mes_ref`: la muestra sale de `fecha_orig`."""
        ruta = tmp_path / "sin_mes.db"
        conn = sqlite3.connect(ruta)
        conn.execute(
            "CREATE TABLE ventas(id_cliente TEXT, fecha_orig TEXT, mes_ref TEXT,"
            " soles REAL, tpo_doc TEXT, serie_doc TEXT, nro_doc TEXT)"
        )
        conn.executemany(
            "INSERT INTO ventas VALUES (?,?,?,?,?,?,?)",
            [
                (f"C{i:03d}", f"2025-03-{i % 9 + 1:02d}", "", 10.0, "FAC", "F01", str(i))
                for i in range(50)
            ],
        )
        conn.commit()
        conn.close()

        monkeypatch.setattr(sys, "argv", ["x", "--db", str(ruta), "--aplicar"])
        assert script.main() == 0
        assert "idx_venta_cliente_fecha" in capsys.readouterr().out

        conn = sqlite3.connect(ruta)
        try:
            assert "idx_venta_cliente_fecha" in _nombres_indices(conn)
        finally:
            conn.close()

    def test_sin_fechas_avisa_y_no_escribe(self, tmp_path, monkeypatch, capsys):
        ruta = tmp_path / "sin_fechas.db"
        conn = sqlite3.connect(ruta)
        conn.execute("CREATE TABLE ventas(id_cliente TEXT, fecha_orig TEXT)")
        conn.execute("INSERT INTO ventas VALUES ('C1', '')")
        conn.commit()
        conn.close()

        monkeypatch.setattr(sys, "argv", ["x", "--db", str(ruta), "--aplicar"])
        assert script.main() == 1
        assert "no puedo medir" in capsys.readouterr().out

        conn = sqlite3.connect(ruta)
        try:
            assert "idx_venta_cliente_fecha" not in _nombres_indices(conn)
        finally:
            conn.close()


def _nombres_indices(conn: sqlite3.Connection) -> set[str]:
    return {
        r[0]
        for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'index' AND tbl_name = 'ventas'"
        ).fetchall()
    }
