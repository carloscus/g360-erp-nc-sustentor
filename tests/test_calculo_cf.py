"""CF de seguimiento en la hoja Cálculo: DIF. UNITARIA y precio histórico.

DIF. UNITARIA > 0 en verde (filas que generan NC), = 0 en gris (se apagan);
precio histórico = 0 en ámbar (sin base no hay con qué comparar). Solo
reglas CellIs sobre el valor (era-2007: las evalúan Excel y LibreOffice).
"""

from openpyxl import load_workbook
from openpyxl.utils import get_column_letter

from src.render.excel_renderer import ExcelRenderer
from tests.test_render_tipos_smoke import TOTALES, _df, _res


def _generar(tmp_path, tipo):
    out = tmp_path / f"{tipo}_cf.xlsx"
    ExcelRenderer().generar(
        _res(_df(tipo), tipo, TOTALES[tipo]),
        str(out),
        tipo=tipo,
        cliente="CLIENTE X",
        doc_ref="F201-100",
    )
    wb = load_workbook(str(out))
    return wb[wb.sheetnames[0]]


def _reglas(ws):
    """{rango: [operadores]} de todas las reglas condicionales."""
    out = {}
    for cf in ws.conditional_formatting:
        out.setdefault(str(cf.sqref), []).extend(rl.operator for rl in cf.rules)
    return out


def _ops(reglas, col, fila):
    """Operadores sobre una celda (openpyxl normaliza F20:F20 → F20)."""
    return reglas.get(f"{col}{fila}:{col}{fila}", reglas.get(f"{col}{fila}", []))


def _fila_encabezado(ws, texto):
    for row in ws.iter_rows():
        if texto in [c.value for c in row]:
            return row[0].row, [c.value for c in row]
    raise AssertionError(f"sin fila de encabezado con {texto!r}")


class TestCfDual:
    """diferencia_precio: tabla 1 (PRECIO UNID.) + tabla 2 (HIST + DIF)."""

    def test_dif_unitaria_verde_y_gris(self, tmp_path):
        ws = _generar(tmp_path, "diferencia_precio")
        r_hdr, headers = _fila_encabezado(ws, "DIF. UNITARIA")
        col = get_column_letter(headers.index("DIF. UNITARIA") + 1)
        reglas = _reglas(ws)
        ops = _ops(reglas, col, r_hdr + 1)
        assert "greaterThan" in ops, "DIF > 0 debe ir en verde"
        assert "equal" in ops, "DIF = 0 debe apagarse en gris"

    def test_precio_hist_efectivo_ambar(self, tmp_path):
        ws = _generar(tmp_path, "diferencia_precio")
        r_hdr, headers = _fila_encabezado(ws, "PRECIO HIST. EFECTIVO")
        col = get_column_letter(headers.index("PRECIO HIST. EFECTIVO") + 1)
        reglas = _reglas(ws)
        assert "equal" in _ops(reglas, col, r_hdr + 1)

    def test_precio_unid_tabla1_ambar(self, tmp_path):
        """El histórico de tabla 1 (COMO SE ATENDIÓ) también se marca."""
        ws = _generar(tmp_path, "diferencia_precio")
        r_hdr, headers = _fila_encabezado(ws, "PRECIO UNID.")
        col = get_column_letter(headers.index("PRECIO UNID.") + 1)
        reglas = _reglas(ws)
        assert "equal" in _ops(reglas, col, r_hdr + 1)


class TestCfSimple:
    """descuento_precio: tabla única (PRECIO ATENDIDO + DIF. UNITARIA)."""

    def test_dif_y_atendido(self, tmp_path):
        ws = _generar(tmp_path, "descuento_precio")
        r_hdr, headers = _fila_encabezado(ws, "DIF. UNITARIA")
        col_dif = get_column_letter(headers.index("DIF. UNITARIA") + 1)
        col_hist = get_column_letter(headers.index("PRECIO ATENDIDO") + 1)
        reglas = _reglas(ws)
        ops_dif = _ops(reglas, col_dif, r_hdr + 1)
        assert "greaterThan" in ops_dif and "equal" in ops_dif
        assert "equal" in _ops(reglas, col_hist, r_hdr + 1)


class TestCfValorCantidad:
    """Monto y cantidad con seguimiento en todos los tipos."""

    def test_monto_verde_y_gris(self, tmp_path):
        ws = _generar(tmp_path, "descuento_precio")
        r_hdr, headers = _fila_encabezado(ws, "MONTO")
        col = get_column_letter(headers.index("MONTO") + 1)
        ops = _ops(_reglas(ws), col, r_hdr + 1)
        assert "greaterThan" in ops, "MONTO > 0 debe ir en verde"
        assert "equal" in ops, "MONTO = 0 debe apagarse en gris"

    def test_cantidad_solo_gris(self, tmp_path):
        ws = _generar(tmp_path, "descuento_precio")
        r_hdr, headers = _fila_encabezado(ws, "CANTIDAD")
        col = get_column_letter(headers.index("CANTIDAD") + 1)
        ops = _ops(_reglas(ws), col, r_hdr + 1)
        assert "equal" in ops, "CANTIDAD = 0 debe apagarse en gris"
        assert "greaterThan" not in ops, "cantidad no lleva verde"

    def test_precio_feria_ambar(self, tmp_path):
        ws = _generar(tmp_path, "feria_preventa")
        r_hdr, headers = _fila_encabezado(ws, "P.U. HIST.")
        col = get_column_letter(headers.index("P.U. HIST.") + 1)
        assert "equal" in _ops(_reglas(ws), col, r_hdr + 1)

    def test_desc_unit_feria_verde_y_gris(self, tmp_path):
        ws = _generar(tmp_path, "feria_preventa")
        r_hdr, headers = _fila_encabezado(ws, "DESC. UNIT.")
        col = get_column_letter(headers.index("DESC. UNIT.") + 1)
        ops = _ops(_reglas(ws), col, r_hdr + 1)
        assert "greaterThan" in ops and "equal" in ops


class TestSinCasillasVacias:
    """El relleno a lo ancho no dibuja casillas: sin borde ni fondo."""

    def test_filler_sin_borde_ni_relleno(self, tmp_path):
        from openpyxl.styles import PatternFill

        ws = _generar(tmp_path, "diferencia_precio")
        # Tabla 1 (7 cols reales) se rellena al ancho de la tabla 2.
        r_hdr, headers = _fila_encabezado(ws, "CANTIDAD")
        n_real = len([h for h in headers if h])
        assert n_real < ws.max_column
        for col in range(n_real + 1, ws.max_column + 1):
            for fila in (r_hdr, r_hdr + 1):
                c = ws.cell(row=fila, column=col)
                assert c.value is None
                assert not (c.border.left.style or c.border.top.style), (fila, col)
                assert c.fill == PatternFill()
