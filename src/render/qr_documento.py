# -*- coding: utf-8 -*-
"""Identidad de documentos: lista de referencias y QR de factura.

Centraliza lo que antes estaba repartido en tres lugares con tres parsers
distintos (``split_doc_id``, ``detector._parsear_referencia_factura`` y el
``split('-')`` a mano del renderer de Excel). Acá vive una sola versión:

- :func:`lista_docs` extrae las facturas referenciadas por un resultado.
- :func:`resolver_qr_factura` decide si corresponde emitir QR SUNAT y con
  qué datos, leyendo el documento SIN el filtro de allowlist de líneas.

Por qué el allowlist importa acá: 424 documentos de la DB tienen líneas
activas y líneas inactivas a la vez (línea 50 está entre las inactivas). El
historial que se carga al reporte solo trae la parte visible, así que el
total de una factura "partida" no se puede tomar de ahí — el QR llevaría
un monto que no corresponde al comprobante y SUNAT no lo validaría. Por eso
el monto sale de ``vw_documento``, que suma todas las líneas.
"""

from __future__ import annotations

import logging
import re
from typing import Optional

from src.core.utils import format_doc_id

logger = logging.getLogger(__name__)

# El único TPO_DOC que es factura común (SUNAT tipo 01). FDI y FEX empiezan
# igual ('F') pero NO son la 01: emitirles QR de factura sería inválido.
TPO_FACTURA = "F01"
TIPO_DOC_SUNAT_FACTURA = "01"

RUC_EMISOR_CIPSA = "20100654025"


# Columnas que pueden llevar un id. de documento de referencia. Se prueban en
# este orden; ``lista_docs`` las unifica en un conjunto único.
_COL_REF_DOC = ("FACTURAS", "FACTURA", "FACTURA_REF", "DOC_ID", "DOCUMENTO")


def lista_docs(df) -> list:
    """Documentos únicos referenciados por un resultado, ordenados.

    Se aceptan solo cadenas que parecen un id. de documento (contienen un
    guión), evitando que un valor suelto (SKU, monto, etc.) se tome por
    referencia.
    """
    docs = set()
    if df is not None and not df.empty:
        for col in _COL_REF_DOC:
            if col not in df.columns:
                continue
            for v in df[col].dropna():
                for p in str(v).replace(";", ",").split(","):
                    p = p.strip().split(" (")[0].strip()
                    if not p or p.lower() in ("nan", "none", ""):
                        continue
                    if "-" not in p:
                        continue
                    docs.add(p)
    return sorted(docs)


def _serie_numero(doc_id: str) -> tuple:
    """(serie, numero) a partir del id concatenado.

    Cubre los tres formatos que circulan en la DB:
      'F204-40088'      (tipo pegado a la serie)
      'F01-204-69002'   (tipo - serie - numero)
      '203-44234'       (sin tipo: la serie lo trae)
    Valores con ruido (espacios, paréntesis) se quitan antes de partir.
    """
    base = str(doc_id).strip().split(" (")[0].strip()
    partes = base.split("-")
    if len(partes) >= 3:
        return partes[1].strip(), partes[2].strip()
    if len(partes) == 2:
        # quita el prefijo de tipo (letras) dejando la serie numérica
        serie = re.sub(r"^[A-Za-z]+", "", partes[0].strip())
        if not serie:
            serie = partes[0].strip()
        return serie, partes[1].strip()
    return "", base


def datos_documento(serie_doc: str, nro_doc: str) -> Optional[dict]:
    """Datos reales de un documento desde ``vw_documento`` (sin allowlist).

    Devuelve None si el documento no está en la DB local.
    """
    try:
        from src.core import ventas_db
    except Exception:  # pragma: no cover - import defensivo
        logger.debug("qr_documento: ventas_db no disponible", exc_info=True)
        return None
    try:
        conn = ventas_db.connect(readonly=True)
    except Exception:
        logger.debug("qr_documento: no se pudo abrir la DB", exc_info=True)
        return None
    try:
        row = conn.execute(
            "SELECT tpo_doc, serie_doc, nro_doc, fecha_orig, doc_cliente, "
            "total_soles, n_lineas FROM vw_documento WHERE serie_doc = ? AND nro_doc = ?",
            (str(serie_doc), str(nro_doc)),
        ).fetchone()
    except Exception:
        logger.debug("qr_documento: consulta fallida", exc_info=True)
        return None
    finally:
        try:
            conn.close()
        except Exception:
            pass
    if not row:
        return None
    return {k: row[k] for k in row.keys()}


def resolver_qr_factura(df, ruc_cliente: str = "") -> Optional[dict]:
    """Payload del QR SUNAT de la factura de referencia, o None.

    Reglas (en este orden; si alguna falla no hay QR):

    1. La NC debe referenciar **exactamente una** factura. Con varias, un
       único QR apuntaría a una de ellas mientras el total corresponde a la
       suma: engaña al auditor. La trazabilidad la dan las columnas
       FACTURA/MONTO de cada línea.
    2. El documento debe existir en la DB local y ser ``F01``. Las boletas
       (``BDI``) y las demás no llevan QR.
    3. El monto es el **total real de la factura**, no el de la NC: el QR
       describe el comprobante que se acredita, no la nota.

    Devuelve dict con: doc_id, tipo_doc, serie, numero, total, fecha, ruc_adq.
    """
    docs = lista_docs(df)
    if len(docs) != 1:
        return None

    serie, numero = _serie_numero(docs[0])
    if not serie or not numero:
        return None

    doc = datos_documento(serie, numero)
    if not doc:
        return None
    total = doc.get("total_soles")
    try:
        total = float(total)
    except (TypeError, ValueError):
        return None
    if total <= 0:
        return None
    fecha = str(doc.get("fecha_orig") or "").strip()
    if not re.match(r"^\d{4}-\d{2}-\d{2}", fecha):
        return None

    tpo = str(doc.get("tpo_doc", "") or "").strip().upper()
    if tpo != TPO_FACTURA:
        return None

    ruc = str(ruc_cliente or "").strip() or str(doc.get("doc_cliente") or "").strip()
    if not ruc or ruc == RUC_EMISOR_CIPSA:
        # sin RUC del adquirente el QR lleva emisor == adquirente y no valida
        return None

    return {
        "doc_id": format_doc_id(tpo, str(serie), str(numero)),
        "tipo_doc": TIPO_DOC_SUNAT_FACTURA,
        "serie": str(serie),
        "numero": str(numero),
        "total": round(float(total), 2),
        "fecha": fecha[:10],
        "ruc_adq": ruc,
    }


def _build_qr_data(payload: dict) -> str:
    """Cadena QR SUNAT: 11 campos pipe-delimited, hash vacío como placeholder."""
    total = float(payload["total"])
    igv = round(total * 0.18 / 1.18, 2)
    return "|".join(
        [
            RUC_EMISOR_CIPSA,
            str(payload["tipo_doc"]),
            str(payload["serie"]),
            str(payload["numero"]),
            f"{igv:.2f}",
            f"{total:.2f}",
            str(payload["fecha"]),
            "6",
            str(payload["ruc_adq"]),
            "",
            "",
        ]
    )


def imagen_qr(payload: dict, size_px: int = 110):
    """PNG del QR a partir del payload. Devuelve BytesIO o None."""
    if not payload:
        return None
    try:
        import qrcode
        from io import BytesIO

        qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_H, box_size=4, border=2)
        qr.add_data(_build_qr_data(payload))
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        img = img.resize((size_px, size_px))
        buf = BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
        return buf
    except Exception:
        logger.debug("qr_documento: no se pudo generar el QR", exc_info=True)
        return None
