"""Aplica idx_venta_cliente_fecha a una DB de ventas existente.

Agrega el compuesto (id_cliente, fecha_orig) que usan todos los fetch por
cliente con rango de fechas (reporte de compras, historial, facturas, pedidos,
O/C). No reconstruye la tabla y es idempotente.

    python -m src.core.agregar_indice_cliente_fecha            # informa
    python -m src.core.agregar_indice_cliente_fecha --aplicar   # crea el indice
    python -m src.core.agregar_indice_cliente_fecha --db RUTA   # otra base

Uso con las apps cerradas: crear el indice escribe sobre los 2.8M de filas y
puede tardar minutos en la base real.
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
import time
from pathlib import Path

from src.core.ventas_db import db_path

INDICE = "idx_venta_cliente_fecha"
DDL = f"CREATE INDEX IF NOT EXISTS {INDICE} ON ventas(id_cliente, fecha_orig)"

# Consulta representativa: el WHERE que arma `_compras_where` y el GROUP BY por
# mes de `_compras_agg`. Si el plan no usa el compuesto, el reporte no mejora.
SQL_MEDICION = (
    "SELECT substr(fecha_orig,1,7), SUM(soles), COUNT(*) FROM ventas "
    "WHERE id_cliente = ? AND fecha_orig >= ? AND fecha_orig <= ? "
    "GROUP BY 1"
)


def _log(msg: str) -> None:
    print(msg, flush=True)


def _tiene_indice(conn: sqlite3.Connection) -> bool:
    return bool(
        conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='index' AND name=?", (INDICE,)
        ).fetchone()
    )


def _muestra(conn: sqlite3.Connection) -> tuple[str, str, str] | None:
    """Cliente y mes con mas filas del ultimo mes con datos.

    `MAX(fecha_orig)` lo resuelve `idx_venta_fecha`, y el conteo por cliente de
    un solo mes es barato. Contar todo `ventas` por cliente costaria un escaneo
    de 2.8M filas solo para elegir la muestra.
    """
    ultima = conn.execute("SELECT MAX(fecha_orig) FROM ventas").fetchone()[0]
    if not ultima:
        return None
    mes = str(ultima)[:7]
    desde, hasta = f"{mes}-01", f"{mes}-31"
    fila = conn.execute(
        "SELECT id_cliente, COUNT(*) FROM ventas "
        "WHERE fecha_orig >= ? AND fecha_orig <= ? "
        "GROUP BY id_cliente ORDER BY 2 DESC LIMIT 1",
        (desde, hasta),
    ).fetchone()
    if not fila or not fila[0]:
        return None
    return str(fila[0]), desde, hasta


def _plan(conn: sqlite3.Connection, muestra: tuple[str, str, str]) -> str:
    filas = conn.execute("EXPLAIN QUERY PLAN " + SQL_MEDICION, muestra).fetchall()
    return " | ".join(r[3] for r in filas)


def _medir(conn: sqlite3.Connection, muestra: tuple[str, str, str]) -> tuple[float, int]:
    """Mejor tiempo de dos corridas (la primera paga cache de SO/paginas)."""
    mejor = float("inf")
    n = 0
    for _ in range(2):
        t = time.perf_counter()
        n = len(conn.execute(SQL_MEDICION, muestra).fetchall())
        mejor = min(mejor, time.perf_counter() - t)
    return mejor, n


def _mb(ruta: Path) -> float:
    try:
        return ruta.stat().st_size / 1024 / 1024
    except OSError:
        return 0.0


def main() -> int:
    ap = argparse.ArgumentParser(description=f"Crea {INDICE} si falta.")
    ap.add_argument("--aplicar", action="store_true", help="escribe (sin esto solo informa)")
    ap.add_argument("--db", default="", help="ruta alterna de la DB")
    args = ap.parse_args()

    ruta = Path(args.db) if args.db else db_path()
    if args.db:
        _log(f"AVISO: usando la base indicada a mano, no la de la app: {ruta}")
    if not ruta.exists():
        _log(f"no existe la DB: {ruta}")
        return 1

    conn = sqlite3.connect(ruta, timeout=30)
    try:
        n_filas = conn.execute("SELECT COUNT(*) FROM ventas").fetchone()[0]
        _log(f"DB: {ruta}  ({_mb(ruta):.0f} MB, {n_filas:,} filas)")
        if n_filas == 0:
            _log("la tabla `ventas` esta vacia: nada que medir ni indexar.")
            return 0

        muestra = _muestra(conn)
        if muestra is None:
            # Con filas pero sin fechas no se puede medir ni tiene sentido
            # fingir que la base esta vacia: se avisa y no se escribe.
            _log("no hay `mes_ref` ni `fecha_orig` poblados: no puedo medir. Nada que hacer.")
            return 1
        cid, desde, hasta = muestra
        _log(f"muestra: cliente {cid}  {desde} .. {hasta}")

        if _tiene_indice(conn):
            _log(f"{INDICE} ya existe: nada que hacer.")
            seg, n = _medir(conn, muestra)
            _log(f"  {n} filas en {seg * 1000:.1f} ms")
            _log(f"  plan: {_plan(conn, muestra)}")
            return 0

        _log(f"plan sin el indice: {_plan(conn, muestra)}")
        seg, n = _medir(conn, muestra)
        _log(f"  {n} filas en {seg * 1000:.1f} ms")

        if not args.aplicar:
            _log("\nsolo informe. Para escribir: --aplicar")
            return 0

        _log(f"creando {INDICE} sobre {n_filas:,} filas...")
        t = time.perf_counter()
        conn.execute(DDL)
        conn.commit()
        _log(f"  indice creado en {time.perf_counter() - t:.1f}s  ({_mb(ruta):.0f} MB)")

        seg, n = _medir(conn, muestra)
        _log(f"  {n} filas en {seg * 1000:.1f} ms")
        plan = _plan(conn, muestra)
        _log(f"  plan: {plan}")
        if INDICE not in plan:
            # El planner sin estadisticas puede preferir el indice simple de
            # id_cliente. Se avisa: no es un error de datos, pero el reporte no
            # gana velocidad hasta correr ANALYZE.
            _log(f"AVISO: el plan no usa {INDICE}; correr `ANALYZE ventas` lo refresca.")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
