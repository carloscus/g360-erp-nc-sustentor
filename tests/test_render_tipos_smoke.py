"""Humo por tipo: todos los reportes DOCX+XLSX generan sin errores.

Cubre los 8 tipos activos con datos mínimos representativos: verifica que
el Excel (tablas + pie PROCESO + pie FACTURAS donde aplica) y el DOCX
(secciones + frase de cierre) salgan completos.
"""

import pathlib
import tempfile

import docx
import pandas as pd
import pytest
from openpyxl import load_workbook

from src.domain import RecognitionResult
from src.render.docx_renderer import DocxInformeRenderer
from src.render.excel_renderer import ExcelRenderer


def _df(tipo):
    base = {
        "SKU": ["S1"],
        "ARTICULO": ["Prod 1"],
        "CANTIDAD": [100],
        "FACTURA": ["F201-100"],
        "ALERTA": ["OK"],
        "CLIENTE": ["CLIENTE X"],
        "DOC_CLIENTE": ["206039928"],
    }
    extra = {
        "diferencia_precio": {
            "SOLES": [340.00],
            "PRECIO_HIST": [3.40],
            "PRECIO_BASE": [3.00],
            "PRECIO_NETO": [3.00],
            "DIFERENCIA": [0.40],
            "MONTO_NC": [40.00],
        },
        "diferencia_cantidad": {
            "SOLES": [340.00],
            "PRECIO_HIST": [3.40],
            "PRECIO_BASE": [3.00],
            "PRECIO_NETO": [3.00],
            "DIFERENCIA": [0.40],
            "MONTO_NC": [40.00],
        },
        "descuento_precio": {
            "SOLES": [340.00],
            "PRECIO_HIST": [3.40],
            "LINEA": ["L01"],
            "%_DESCUENTO": [0.05],
            "PRECIO_NETO": [3.23],
            "DIFERENCIA": [0.17],
            "MONTO_NC": [17.00],
        },
        "descuento_factura": {
            "PRECIO_UNITARIO": [3.40],
            "%_DESCUENTO": [0.05],
            "MONTO_NC": [17.00],
        },
        "bonificacion_promocion": {
            "FACTURAS": ["F201-100"],
            "CICLOS": [12],
            "BONIFICACION": [8],
            "PRECIO_UNITARIO": [3.40],
            "MONTO_NC": [27.20],
        },
        "rebate_volumen": {
            "LINEA": ["L01"],
            "SKUS": ["S1"],
            "MONTO_BASE": [1000.00],
            "%_DEL_TOTAL": [100.0],
            "%_REBATE": [0.05],
            "MONTO_NC": [50.00],
        },
        "anular_factura": {
            "PRECIO_HIST": [3.40],
            "MONTO_FACTURA": [340.00],
            "MONTO_NC": [340.00],
        },
        "feria_preventa": {
            "LINEA": ["L01"],
            "Cant. Solicitada": [120],
            "Cant. Sustentada": [100],
            "P.U. Hist.": [3.40],
            "P.U. Result.": [3.23],
            "Desc. Unit. (S/)": [0.17],
            "Tot. Sustento (S/)": [323.00],
            "Subtotal NC (S/)": [17.00],
            "FACTURAS": ["F201-100"],
            "Cant. Facturada": [100],
            "Cant. Disponible": [100],
            "% Stock Restante": [120.0],
            "Glosa": ["OK"],
        },
        "diferencia_stock": {
            "Cantidad Facturada": [100],
            "Stock Cliente": [60],
            "Stock Sustentado": [60],
            "% Stock Restante": [60.0],
            "PRECIO_HIST": [3.40],
            "Precio Lista": [3.00],
            "Precio Neto": [3.00],
            "Dif. Unitaria": [0.40],
            "MONTO_NC": [24.00],
        },
    }
    d = dict(base)
    d.update(extra[tipo])
    return pd.DataFrame(d)


def _res(df, tipo, total):
    return RecognitionResult(
        dataframe=df,
        dataframe_excel=df.copy(),
        resumen={
            "total_nc": total,
            "skus_afectados": 1,
            "doc_ref": "F201-101" if tipo == "rebate_volumen" else "F201-100",
        },
    )


def _docx_texto(path):
    doc = docx.Document(str(path))
    pars = [p.text for p in doc.paragraphs if p.text.strip()]
    tabs = [c.text for t in doc.tables for r in t.rows for c in r.cells]
    return pars, tabs


TIPOS = [
    "diferencia_precio",
    "diferencia_cantidad",
    "descuento_precio",
    "descuento_factura",
    "bonificacion_promocion",
    "rebate_volumen",
    "anular_factura",
    "feria_preventa",
    "diferencia_stock",
]
TOTALES = {
    "diferencia_precio": 40.00,
    "diferencia_cantidad": 40.00,
    "descuento_precio": 17.00,
    "descuento_factura": 17.00,
    "bonificacion_promocion": 27.20,
    "rebate_volumen": 50.00,
    "anular_factura": 340.00,
    "feria_preventa": 17.00,
    "diferencia_stock": 24.00,
}


class TestHumoExcel:
    def _generar(self, tmp_path, tipo, **kw):
        df = _df(tipo)
        out = tmp_path / f"{tipo}_Calculo.xlsx"
        ExcelRenderer().generar(
            _res(df, tipo, TOTALES[tipo]),
            str(out),
            tipo=tipo,
            cliente="CLIENTE X",
            doc_ref="F201-100",
            ruc="206039928",
            modalidad=kw.get("modalidad", "individual"),
        )
        wb = load_workbook(str(out))
        ws = wb[wb.sheetnames[0]]
        return [c.value for row in ws.iter_rows() for c in row if isinstance(c.value, str)]

    def test_todos_generan_tabla(self, tmp_path):
        for tipo in TIPOS:
            textos = self._generar(tmp_path, tipo)
            assert "SKU" in textos or "LÍNEA" in textos, tipo
            assert "PROCESO APLICADO" not in textos, tipo

    def test_columna_a_ancho_15(self, tmp_path):
        from openpyxl import load_workbook
        from src.render.excel_renderer import ExcelRenderer

        df = _df("diferencia_precio")
        out = tmp_path / "C.xlsx"
        ExcelRenderer().generar(
            _res(df, "diferencia_precio", 40.00),
            str(out),
            tipo="diferencia_precio",
            cliente="C",
            doc_ref="F201-100",
        )
        wb = load_workbook(str(out))
        ws = wb[wb.sheetnames[0]]
        assert ws.column_dimensions["A"].width == 15
        assert ws.page_margins.left == 0.8
        assert ws.page_margins.right == 0.8

    def test_facturas_comprometidas_solo_con_resumen(self, tmp_path):
        from src.domain import RecognitionResult

        df = _df("diferencia_precio")
        res = RecognitionResult(
            dataframe=df,
            dataframe_excel=df.copy(),
            resumen={
                "total_nc": 40.00,
                "skus_afectados": 1,
                "doc_ref": "F201-100",
                "documentos_unicos": ["F201-100"],
                "titulo_documentos": "FACTURAS COMPROMETIDAS",
            },
        )
        out = tmp_path / "C.xlsx"
        ExcelRenderer().generar(
            res,
            str(out),
            tipo="diferencia_precio",
            cliente="C",
            doc_ref="F201-100",
            modalidad="consolidado",
        )
        wb = load_workbook(str(out))
        ws = wb[wb.sheetnames[0]]
        textos = [c.value for row in ws.iter_rows() for c in row if isinstance(c.value, str)]
        assert "FACTURAS COMPROMETIDAS: F201-100" in textos

    @pytest.mark.parametrize("tipo", ["diferencia_precio", "diferencia_cantidad"])
    def test_consolidado_usa_columna_facturas(self, tmp_path, tipo):
        """El swap FACTURA -> FACTURAS solo estaba activo para DC.

        En consolidado cada fila agrupa varias facturas: sin el swap la
        columna mostraba unico documento y se perdian los demas.
        """
        df = _df(tipo)
        df["FACTURAS"] = ["F201-100, F201-101"]
        out = tmp_path / f"{tipo}_conso.xlsx"
        ExcelRenderer().generar(
            _res(df, tipo, TOTALES[tipo]),
            str(out),
            tipo=tipo,
            cliente="C",
            doc_ref="F201-100",
            modalidad="consolidado",
        )
        wb = load_workbook(str(out))
        ws = wb[wb.sheetnames[0]]
        textos = [c.value for row in ws.iter_rows() for c in row if isinstance(c.value, str)]
        assert "FACTURAS" in textos, f"{tipo}: no se escribio FACTURAS"
        assert "F201-100, F201-101" in textos, f"{tipo}: se perdio el listado"

    def test_do_consolidado_usa_columna_facturas(self, tmp_path):
        """DO comparte el swap aunque su tabla sea una lista plana de columnas."""
        from src.render.excel_renderer import columnas_consolidadas_dc, COLUMNAS_POR_TIPO

        col_defs = columnas_consolidadas_dc(COLUMNAS_POR_TIPO["descuento_precio"])
        headers = [c["header"] for c in col_defs]
        assert "FACTURAS" in headers and "FACTURA" not in headers
        # la lista original no se muta
        assert [c["header"] for c in COLUMNAS_POR_TIPO["descuento_precio"]][1] == "FACTURA"

    def test_feria_preventa_escribe_cobertura_de_cantidades(self, tmp_path):
        """FPE reporta facturado / disponible / % restante por SKU (como VRS)."""
        df = _df("feria_preventa")
        out = tmp_path / "FPE.xlsx"
        ExcelRenderer().generar(
            _res(df, "feria_preventa", 17.00),
            str(out),
            tipo="feria_preventa",
            cliente="C",
            doc_ref="F201-100",
        )
        wb = load_workbook(str(out))
        ws = wb[wb.sheetnames[0]]
        grid = [[c.value for c in row] for row in ws.iter_rows()]
        head = next(i for i, r in enumerate(grid) if "CANT. SUST." in r)
        headers = grid[head]
        assert "CANT. FACTURADA" in headers
        assert "CANT. DISPONIBLE" in headers
        assert "% STOCK REST." in headers
        fila = grid[head + 1]
        assert fila[headers.index("CANT. FACTURADA")] == 100
        assert fila[headers.index("% STOCK REST.")] == 120.0


class TestHumoDocx:
    def _generar(self, tmp_path, tipo, **kw):
        df = _df(tipo)
        out = tmp_path / f"{tipo}_Informe.docx"
        datos = {
            "tipo_operacion": "DC",
            "tipo_calculo": tipo,
            "cliente": "CLIENTE X",
            "representante": "V",
            "numero_referencia": "F201-100",
            "evidencias": {},
            "modalidad": kw.get("modalidad", "individual"),
            "periodo": "01/01/2026 al 31/01/2026",
            "descripcion": "caso de prueba",
            "observaciones": "sin observaciones",
        }
        DocxInformeRenderer().generar(
            _res(df, tipo, TOTALES[tipo]),
            ruta_salida=str(out),
            datos_adicionales=datos,
            nombre_archivo_excel="C.xlsx",
        )
        return _docx_texto(out)

    def test_todos_generan_secciones(self, tmp_path):
        for tipo in TIPOS:
            pars, _ = self._generar(tmp_path, tipo)
            for sec in (
                "1. DATOS GENERALES",
                "2. RESULTADO ECON",
                "3. ANTECEDENTES",
                "4. OBSERVACIONES",
                "5. DOCUMENTOS",
            ):
                assert any(sec in p for p in pars), (tipo, sec)
            assert not any("PROCESO APLICADO" in p for p in pars), tipo

    def test_frase_cierre_todos(self, tmp_path):
        claves = {
            "diferencia_precio": "histórico",
            "diferencia_cantidad": "cantidad exacta",
            "descuento_precio": "omitidos",
            "descuento_factura": "omitidos",
            "bonificacion_promocion": "bonificación",
            "rebate_volumen": "rebate",
            "anular_factura": "anula",
            "feria_preventa": "feria",
            "diferencia_stock": "SKU",
        }
        for tipo in TIPOS:
            pars, _ = self._generar(tmp_path, tipo)
            assert any("S/" in p and claves[tipo] in p for p in pars), tipo


class TestFechaFueraDeAlertas:
    """La fecha no debe vivir en una columna de ALERTA/AUDITORÍA/GLOSA.

    Andaba en la esquina superior derecha (última columna), que es justo
    donde están esas columnas: al ocultarlas o borrarlas para la
    presentación final la fecha desaparecía con ellas. Ahora es un campo
    más del panel "DATOS DE LA OPERACIÓN".
    """

    RIESGO = {"ALERTA", "AUDITORÍA", "GLOSA"}
    DUALES = {"diferencia_precio", "diferencia_cantidad", "diferencia_stock"}

    def _celdas(self, tipo, n_desc=0):
        from openpyxl.utils import get_column_letter
        from src.render.excel_renderer import ExcelRenderer

        df = _df(tipo)
        for i in range(1, n_desc + 1):
            df[f"DESC{i}"] = [0.02 * i]
        out = pathlib.Path(tempfile.mkdtemp()) / "c.xlsx"
        ExcelRenderer().generar(
            _res(df, tipo, TOTALES[tipo]),
            str(out),
            tipo=tipo,
            cliente="CLIENTE X",
            doc_ref="F201-100",
            ruc="206039928",
        )
        wb = load_workbook(str(out))
        ws = wb[wb.sheetnames[0]]
        # la celda de la fecha: la de al lado del rótulo "Fecha"
        rotulo = [c for row in ws.iter_rows() for c in row if c.value == "Fecha"]
        fechas = [ws.cell(row=rotulo[0].row, column=rotulo[0].column + 1)] if rotulo else []
        riesgo = {c.column for row in ws.iter_rows() for c in row if c.value in self.RIESGO}
        return ws, rotulo, fechas, riesgo, get_column_letter

    def test_fecha_es_campo_del_panel_y_no_esta_en_columna_de_alerta(self):
        for tipo in TIPOS:
            for n_desc in (0, 1, 3) if tipo in self.DUALES else (0,):
                ws, rotulo, fechas, riesgo, letra = self._celdas(tipo, n_desc)
                assert len(rotulo) == 1, (tipo, n_desc)
                assert len(fechas) == 1, (tipo, n_desc)
                assert fechas[0].value, (tipo, n_desc)
                assert rotulo[0].column == 3, (tipo, n_desc, letra(rotulo[0].column))
                assert rotulo[0].column not in riesgo, (tipo, n_desc)

    def test_fecha_no_esta_en_la_fila_de_totales(self):
        """El pie junto a los totales queda libre (ahí irá el QR en individual)."""
        for tipo in TIPOS:
            for n_desc in (0, 1, 3) if tipo in self.DUALES else (0,):
                ws, rotulo, fechas, riesgo, letra = self._celdas(tipo, n_desc)
                fila_total = [
                    c.row for row in ws.iter_rows() for c in row if c.value == "TOTAL (con IGV):"
                ]
                # aparece dos veces: en el panel del header y en el bloque de
                # totales al pie. Va con el del pie (el último).
                assert len(fila_total) == 2, (tipo, n_desc, fila_total)
                assert fechas[0].row != fila_total[-1], (tipo, n_desc)

    def test_panel_izquierdo_conserva_su_titulo_a_d(self):
        for tipo in TIPOS:
            ws, rotulo, fechas, riesgo, letra = self._celdas(tipo)
            merges = {str(m) for m in ws.merged_cells.ranges if m.min_row == 3}
            assert "A3:D3" in merges, (tipo, merges)
            assert "F3:G3" in merges, (tipo, merges)

    def test_qr_no_cae_en_columna_de_alerta(self):
        """Si se emite, el QR va junto a los totales, fuera de zona de alertas."""
        from src.render.qr_documento import resolver_qr_factura

        ws, rotulo, fechas, riesgo, letra = self._celdas("anular_factura")
        payload = resolver_qr_factura(_df("anular_factura"), "206039928")
        if payload is None:
            assert not ws._images, "hay QR sin payload"
            return
        assert ws._images, "había payload y no se dibujó el QR"
        col_qr = ws._images[0].anchor._from.col + 1
        assert col_qr not in riesgo, (letra(col_qr), sorted(riesgo))


class TestQrEnHeader:
    """El QR va en la banda del header (filas 3-9), fuera de zona de alertas.

    Se verifica el `ext` del XML guardado y NO `img.width`: openpyxl al
    cargar recalcula el ancho desde el PNG e ignora el tamaño real con el
    que se dibujó, y esa lectura mintió durante el desarrollo (reportaba
    110 px donde el archivo tenía 96).
    """

    PAYLOAD = {
        "doc_id": "F204-1",
        "tipo_doc": "01",
        "serie": "204",
        "numero": "1",
        "total": 100.0,
        "fecha": "2026-10-02",
        "ruc_adq": "206039928",
    }

    def _generar(self, tipo, tmp_path, monkeypatch):
        import zipfile
        import re

        from openpyxl.utils import get_column_letter
        from src.render import excel_renderer
        from src.render.excel_renderer import QR_MIN_PX, ExcelRenderer

        # excel_renderer importa el resolver a su propio namespace: hay que
        # parchearlo ahí, no en qr_documento.
        monkeypatch.setattr(
            excel_renderer,
            "resolver_qr_factura",
            lambda df, ruc="": dict(self.PAYLOAD),
        )
        out = tmp_path / f"{tipo}.xlsx"
        ExcelRenderer().generar(
            _res(_df(tipo), tipo, TOTALES[tipo]),
            str(out),
            tipo=tipo,
            cliente="C",
            doc_ref="F204-1",
            ruc="206039928",
        )
        with zipfile.ZipFile(out) as z:
            names = [n for n in z.namelist() if re.match(r"xl/drawings/drawing\d+\.xml", n)]
            assert names, f"{tipo}: no se genero dibujo"
            xml = z.read(names[0]).decode("utf-8")
        col = int(re.search(r"<col>(\d+)</col>", xml).group(1)) + 1
        row = int(re.search(r"<row>(\d+)</row>", xml).group(1)) + 1
        px = int(re.search(r'cx="(\d+)"', xml).group(1)) / 9525
        ws = load_workbook(str(out)).worksheets[0]
        alertas = sorted(
            {
                c.column
                for row in ws.iter_rows()
                for c in row
                if c.value in ("ALERTA", "AUDITORÍA", "GLOSA")
            }
        )
        return ws, col, row, px, alertas, QR_MIN_PX

    def test_qr_esta_en_la_banda_del_header(self, tmp_path, monkeypatch):
        for tipo in TIPOS:
            ws, col, row, px, alertas, _ = self._generar(tipo, tmp_path, monkeypatch)
            assert row == 3, (tipo, row)
            # el header arranca en la columna H: A:D es el panel izquierdo y
            # F:G el de TOTALES
            assert col >= 5, (tipo, col)

    def test_qr_no_invade_una_columna_de_alerta(self, tmp_path, monkeypatch):
        from openpyxl.utils import get_column_letter

        for tipo in TIPOS:
            ws, col, row, px, alertas, _ = self._generar(tipo, tmp_path, monkeypatch)
            acum = 0
            fin = col
            while acum < px and fin <= ws.max_column:
                w = ws.column_dimensions[get_column_letter(fin)].width or 8.43
                acum += round(w * 7) + 5
                fin += 1
            invade = [a for a in alertas if col < a <= fin - 1]
            assert not invade, (tipo, col, fin - 1, alertas)

    def test_qr_nunca_baja_del_piso_legible(self, tmp_path, monkeypatch):
        for tipo in TIPOS:
            ws, col, row, px, alertas, minimo = self._generar(tipo, tmp_path, monkeypatch)
            assert px >= minimo, (tipo, px, minimo)


class TestReglasQrFactura:
    """El QR sale solo con UNA factura de referencia y solo si es F01."""

    def _df(self, facturas):
        import pandas as pd

        return pd.DataFrame(
            {
                "FACTURA": facturas,
                "CANTIDAD": [100] * len(facturas),
                "MONTO_NC": [40.0] * len(facturas),
            }
        )

    def test_varias_facturas_no_llevan_qr(self, monkeypatch):
        from src.render import qr_documento

        monkeypatch.setattr(
            qr_documento,
            "datos_documento",
            lambda s, n: {
                "tpo_doc": "F01",
                "serie_doc": s,
                "nro_doc": n,
                "fecha_orig": "2026-10-02",
                "doc_cliente": "206039928",
                "total_soles": 340.0,
                "n_lineas": 2,
            },
        )
        df = self._df(["F01-204-1", "F01-204-2"])
        assert qr_documento.resolver_qr_factura(df, "206039928") is None

    def test_boleta_no_lleva_qr(self, monkeypatch):
        from src.render import qr_documento

        monkeypatch.setattr(
            qr_documento,
            "datos_documento",
            lambda s, n: {
                "tpo_doc": "BDI",
                "serie_doc": s,
                "nro_doc": n,
                "fecha_orig": "2026-10-02",
                "doc_cliente": "206039928",
                "total_soles": 340.0,
                "n_lineas": 2,
            },
        )
        df = self._df(["203-44234"])
        assert qr_documento.resolver_qr_factura(df, "206039928") is None

    def test_fdi_no_lleva_qr_aunque_empiece_con_f(self, monkeypatch):
        """FDI y FEX arrancan con 'F' pero no son la factura tipo 01."""
        from src.render import qr_documento

        for tpo in ("FDI", "FEX"):
            monkeypatch.setattr(
                qr_documento,
                "datos_documento",
                lambda s, n, t=tpo: {
                    "tpo_doc": t,
                    "serie_doc": s,
                    "nro_doc": n,
                    "fecha_orig": "2026-10-02",
                    "doc_cliente": "206039928",
                    "total_soles": 340.0,
                    "n_lineas": 2,
                },
            )
            df = self._df([f"{tpo}2-1"])
            assert qr_documento.resolver_qr_factura(df, "206039928") is None, tpo

    def test_una_factura_f01_si_lleva_qr_con_el_total_real(self, monkeypatch):
        from src.render import qr_documento

        monkeypatch.setattr(
            qr_documento,
            "datos_documento",
            lambda s, n: {
                "tpo_doc": "F01",
                "serie_doc": s,
                "nro_doc": n,
                "fecha_orig": "2026-10-02",
                "doc_cliente": "206039928",
                "total_soles": 340.0,
                "n_lineas": 2,
            },
        )
        df = self._df(["F01-204-69002"])
        p = qr_documento.resolver_qr_factura(df, "206039928")
        assert p is not None
        # el total es el de la FACTURA (340), no el de la NC (40)
        assert p["total"] == 340.0
        assert p["tipo_doc"] == "01"
        assert p["doc_id"] == "F204-69002"

    def test_sin_ruc_del_adquirente_no_lleva_qr(self, monkeypatch):
        from src.render import qr_documento

        monkeypatch.setattr(
            qr_documento,
            "datos_documento",
            lambda s, n: {
                "tpo_doc": "F01",
                "serie_doc": s,
                "nro_doc": n,
                "fecha_orig": "2026-10-02",
                "doc_cliente": "206039928",
                "total_soles": 340.0,
                "n_lineas": 2,
            },
        )
        df = self._df(["F01-204-69002"])
        # sin RUC, cae al doc_cliente de la factura: hay QR
        assert qr_documento.resolver_qr_factura(df, "") is not None
        # con RUC igual al emisor, el QR no validaría: se omite
        assert qr_documento.resolver_qr_factura(df, qr_documento.RUC_EMISOR_CIPSA) is None


class TestSimetriaColumnas:
    """Todas las bandas del reporte deben cerrar en la misma columna.

    En los casos de dos tablas cada una ocupaba solo lo que necesitaba y las
    barras de título quedaban a distinto largo (el reporte se veía en
    escalera). Ahora ambas se rellenan al ancho común y el pie también.
    """

    DUALES = ("diferencia_precio", "diferencia_cantidad", "diferencia_stock")

    def _ws(self, tmp_path, tipo, n_desc=0):
        from src.render.excel_renderer import ExcelRenderer

        df = _df(tipo)
        for i in range(1, n_desc + 1):
            df[f"DESC{i}"] = [0.02 * i]
        out = tmp_path / f"{tipo}_{n_desc}.xlsx"
        ExcelRenderer().generar(
            _res(df, tipo, TOTALES[tipo]),
            str(out),
            tipo=tipo,
            cliente="CLIENTE X",
            doc_ref="F201-100",
            ruc="206039928",
        )
        wb = load_workbook(str(out))
        return wb[wb.sheetnames[0]]

    def _bandas_ancho_completo(self, ws):
        """Merges de una sola fila que arrancan en A y cruzan el reporte entero.

        Se excluye la fila 3: ahí el bloque de cabecera es intencionalmente
        bilateral (DATOS DE LA OPERACIÓN | TOTALES), no una banda a lo ancho.
        """
        return [
            m
            for m in ws.merged_cells.ranges
            if m.min_col == 1 and m.max_row == m.min_row and m.min_row != 3
        ]

    def test_todas_las_bandas_terminan_en_la_misma_columna(self, tmp_path):
        for tipo in TIPOS:
            ws = self._ws(tmp_path, tipo)
            anchas = self._bandas_ancho_completo(ws)
            assert anchas, tipo
            assert len({m.max_col for m in anchas}) == 1, (tipo, [str(m) for m in anchas])

    def test_tablas_duales_ocupan_el_mismo_ancho(self, tmp_path):
        for tipo in self.DUALES:
            for n_desc in (0, 1, 3):
                ws = self._ws(tmp_path, tipo, n_desc)
                titulos = [
                    m
                    for m in self._bandas_ancho_completo(ws)
                    if str(ws.cell(row=m.min_row, column=1).value or "")[:1].isdigit()
                ]
                assert titulos, (tipo, n_desc)
                assert len({m.max_col for m in titulos}) == 1, (
                    tipo,
                    n_desc,
                    [str(m) for m in titulos],
                )

    def test_relleno_no_agrega_texto_ni_desplaza_formulas(self, tmp_path):
        """La tabla 1 se rellena a lo ancho, pero sin celdas con contenido."""
        from openpyxl.utils import get_column_letter

        ws = self._ws(tmp_path, "diferencia_stock", 1)
        # la última columna es relleno: sin encabezado y sin dato
        assert ws.cell(row=13, column=ws.max_column).value is None
        assert ws.cell(row=14, column=ws.max_column).value is None

        # las fórmulas siguen apuntando a las columnas de siempre:
        # MONTO = DIF. UNITARIA x CANT. SOLICITADA (F) de la tabla 1
        # DIF. UNITARIA = PRECIO C/AJUSTE (I, tabla 1) - PRECIO NETO
        headers = {ws.cell(row=19, column=c).value: c for c in range(1, ws.max_column + 1)}
        col_monto = headers["MONTO (Sin IGV)"]
        col_dif = headers["DIF. UNITARIA"]
        col_neto = headers["PRECIO NETO"]
        assert ws.cell(row=20, column=col_monto).value == (
            f"=ROUND({get_column_letter(col_dif)}20*F14,2)"
        )
        assert ws.cell(row=20, column=col_dif).value == (
            f"=MAX(0,ROUND(I14-{get_column_letter(col_neto)}20,5))"
        )


class TestEstadoAlerta:
    def test_al13_fuerte_es_error_rojo(self):
        r = ExcelRenderer()
        fuerte = "AL13 - NC ACUMULADAS EXCEDEN VALOR FACTURA"
        assert r._estado(fuerte) == "ERROR"
        assert r._estado("AL12 - NC APLICADA") == "ALERTA"
        assert r._estado("AL02 - Precios coinciden") == "INFO"
        assert r._estado("OK") == "OK"


class TestTablaVrsBreve:
    def test_tabla1_vrs_sin_redundancia_y_con_doble_precio(self, tmp_path):
        """Tabla 1 VRS breve: sin CANT. FACTURADA ni % STOCK RESTANTE,
        con STOCK renombrado y doble columna de precio."""
        from openpyxl import load_workbook

        df = _df("diferencia_stock")
        out = tmp_path / "vrs_breve.xlsx"
        ExcelRenderer().generar(
            _res(df, "diferencia_stock", 24.00),
            str(out),
            tipo="diferencia_stock",
            cliente="CLIENTE X",
            doc_ref="F201-100",
        )
        wb = load_workbook(str(out))
        ws = wb[wb.sheetnames[0]]
        grid = [[c.value for c in row] for row in ws.iter_rows()]
        head = next(
            i for i, r in enumerate(grid) if "CANT. DISPONIBLE" in r and "UNIDADES A RECONOCER" in r
        )
        headers = [h for h in grid[head] if h]
        assert headers == [
            "N°",
            "FACTURA",
            "SKU",
            "ARTICULO",
            "CANT. DISPONIBLE",
            "CANT. SOLICITADA",
            "UNIDADES A RECONOCER",
            "PRECIO FACTURA",
            "PRECIO C/AJUSTE",
        ]
        assert "CANT. FACTURADA" not in grid[head]
        assert "% STOCK RESTANTE" not in grid[head]
        fila = grid[head + 1]
        # PRECIO C/AJUSTE trae el histórico del motor (3.40 del fixture).
        assert fila[headers.index("PRECIO C/AJUSTE")] == 3.40
