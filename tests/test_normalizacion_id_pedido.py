"""`id_pedido` normalizado al entrar, no al leer.

El barrido masivo (`LIKE '% %'`) no puede usar índice: escanea las 2.8M de
filas. Medido en la base real: 67 s y 0 filas cambiadas, en CADA init_db().
Por eso la regla vive en el punto de entrada y el barrido queda como
reparación única de bases anteriores, marcada en `_migracion_id_pedido`.
"""

import sqlite3

from src.core import ventas_db


def _fila(conn: sqlite3.Connection, folio: str) -> str:
    return conn.execute("SELECT id_pedido FROM ventas WHERE folio_unico = ?", (folio,)).fetchone()[
        0
    ]


class TestEntrada:
    def test_insert_ventas_normaliza(self, tmp_db, sample_ventas):
        conn = tmp_db.get_conn()
        fila = dict(sample_ventas[0], id_pedido="SADIE 25", folio_unico="T-1")
        tmp_db.insert_ventas(conn, [fila], label="2024-01-15")
        assert _fila(conn, "T-1") == "SADIE_25"

    def test_replace_folios_normaliza(self, tmp_db, sample_ventas):
        conn = tmp_db.get_conn()
        fila = dict(sample_ventas[0], id_pedido="SADIE  25 X", folio_unico="T-2")
        tmp_db.replace_folios(conn, [fila])
        assert _fila(conn, "T-2") == "SADIE_25_X"

    def test_vacio_y_none_no_se_rompen(self, tmp_db, sample_ventas):
        conn = tmp_db.get_conn()
        filas = [
            dict(sample_ventas[0], id_pedido="", folio_unico="T-3"),
            dict(sample_ventas[0], id_pedido=None, folio_unico="T-4"),
        ]
        tmp_db.insert_ventas(conn, filas, label="2024-01-16")
        assert _fila(conn, "T-3") == ""
        assert _fila(conn, "T-4") is None

    def test_normaliza_id_pedido_fila_para_copias(self):
        cols = ["id_cliente", "id_pedido", "fecha_orig"]
        fila = ("C1", "SADIE 25", "2024-01-01")
        assert ventas_db.normaliza_id_pedido_fila(fila, cols) == (
            "C1",
            "SADIE_25",
            "2024-01-01",
        )
        # Sin espacios o sin la columna: devuelve la misma fila (idempotente).
        assert ventas_db.normaliza_id_pedido_fila(
            ("C1", "SADIE_25"), ["id_cliente", "id_pedido"]
        ) == (
            "C1",
            "SADIE_25",
        )
        assert ventas_db.normaliza_id_pedido_fila(("C1",), ["id_cliente"]) == ("C1",)


class TestBarrido:
    def _sembrar_crudo(self, conn: sqlite3.Connection, fila: dict, folio: str) -> None:
        """Inserta por SQL directo: simula una base vieja, sin pasar por
        `_preparar_fila`."""
        v = dict(fila, id_pedido="SADIE 25", folio_unico=folio)
        cols = ventas_db.INSERT_COLS.split(",")
        conn.execute(
            f"INSERT INTO ventas ({ventas_db.INSERT_COLS}) VALUES ({','.join('?' * len(cols))})",
            [v.get(c) for c in cols],
        )
        conn.commit()

    def test_corre_una_vez_y_marca(self, tmp_db, sample_ventas):
        conn = tmp_db.get_conn()
        # El fixture ya corrió init_db sobre base vacía: el marcador existe.
        conn.execute("DELETE FROM _migracion_id_pedido")
        conn.commit()
        self._sembrar_crudo(conn, sample_ventas[0], "V-1")
        assert _fila(conn, "V-1") == "SADIE 25"

        tmp_db.init_db()
        assert _fila(conn, "V-1") == "SADIE_25"
        assert tmp_db._barrido_id_pedido_hecho(conn) is True

        # Segunda pasada: no vuelve a barrer. Si lo hiciera, esta fila cambiaría.
        self._sembrar_crudo(conn, sample_ventas[0], "V-2")
        tmp_db.init_db()
        assert _fila(conn, "V-2") == "SADIE 25"

    def test_marcar_evita_el_barrido(self, tmp_db, sample_ventas):
        """Las rutas que ya copian normalizado marcan sin escanear."""
        conn = tmp_db.get_conn()
        conn.execute("DELETE FROM _migracion_id_pedido")
        conn.commit()
        self._sembrar_crudo(conn, sample_ventas[0], "V-9")

        tmp_db.marcar_barrido_id_pedido(conn)
        conn.commit()
        tmp_db.init_db()
        assert _fila(conn, "V-9") == "SADIE 25"

    def test_marcador_no_rompe_el_contrato(self, tmp_db):
        conn = tmp_db.get_conn()
        rep = tmp_db.verificar_contrato(conn)
        assert rep["tablas_extra_no_toleradas"] == []
        assert "_migracion_id_pedido" in rep["tablas_auditoria"]


class TestCopiasEntreBases:
    def _db_origen(self, ruta, fila: dict, folio: str) -> None:
        conn = sqlite3.connect(ruta)
        conn.executescript(ventas_db.CREATE_TABLE_VENTAS)
        cols = ventas_db.INSERT_COLS.split(",")
        v = dict(fila, id_pedido="SADIE 25", folio_unico=folio)
        conn.execute(
            f"INSERT INTO ventas ({ventas_db.INSERT_COLS}) VALUES ({','.join('?' * len(cols))})",
            [v.get(c) for c in cols],
        )
        conn.commit()
        conn.close()

    def test_cartucho_parcial_normaliza_y_marca(self, tmp_path, sample_ventas):
        """Un cartucho viejo con `id_pedido` sucio no ensucia al receptor."""
        from src.core import cartucho

        src = tmp_path / "origen.db"
        self._db_origen(src, sample_ventas[0], "P-1")
        dst = tmp_path / "parcial.db"

        cartucho._db_parcial(src, dst, "2010-01-01", "2030-12-31")

        conn = sqlite3.connect(dst)
        try:
            assert (
                conn.execute("SELECT id_pedido FROM ventas WHERE folio_unico = 'P-1'").fetchone()[0]
                == "SADIE_25"
            )
            assert ventas_db._barrido_id_pedido_hecho(conn) is True
        finally:
            conn.close()
