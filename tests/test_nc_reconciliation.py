"""Invoice/SKU NC reconciliation rules used by price difference."""

import pandas as pd

from src.core.nc_reconciliation import reconciliar_notas


def _historial(*notas):
    base = [
        {
            "TIPO_DOC": "F01",
            "TIPO_CLASE": "factura",
            "SERIE": "001",
            "NUMERO": "10",
            "DOC_ID": "F001-10",
            "FACTURA_REF": "",
            "CODIGO": "00123",
            "CANTIDAD": 100.0,
            "SOLES": 1000.0,
            "CANTIDAD_FAE": 0.0,
            "REFERENCIA": "",
        }
    ]
    for i, nota in enumerate(notas, 1):
        base.append(
            {
                "TIPO_DOC": nota.get("tipo", "NCR"),
                "TIPO_CLASE": nota.get("clase", "descuento"),
                "SERIE": "N001",
                "NUMERO": str(i),
                "DOC_ID": f"NCRN001-{i}",
                "DOC_NOTA": f"NCRN001-{i}",
                "FACTURA_REF": "F001-10",
                "CODIGO": nota.get("sku", "00123"),
                "CANTIDAD": nota.get("cantidad", 0.0),
                "CANTIDAD_FAE": nota.get("fae", 0.0),
                "SOLES": nota.get("soles", -100.0),
                "REFERENCIA": "F01/001-10",
            }
        )
    return pd.DataFrame(base)


def _policy(*, use_nc=True, use_ndb=True):
    return {
        "facturas": {"mostrar": True, "usar": True},
        "nc": {"mostrar": True, "usar": use_nc},
        "ndb": {"mostrar": True, "usar": use_ndb},
    }


def _result(df, *, docs=None, modality="individual", **kw):
    out = reconciliar_notas(df, documentos=docs or _policy(), modalidad=modality)
    return out[("F001-10", "123")]


def test_fae_exacta_adjusts_signed_value_only_in_individual():
    rec = _result(_historial({"fae": 100, "soles": -100}))
    assert rec["delta_soles"] == -100
    assert rec["qty_return"] == 0
    assert rec["applied"] is True
    assert rec["details"][0]["estado"] == "exacta"
    assert rec["details"][0]["valor_unitario"] == 1


def test_partial_fae_is_manual_review_not_adjusted_even_if_enabled():
    rec = _result(_historial({"fae": 60, "soles": -60}))
    assert rec["delta_soles"] == 0
    assert rec["qty_return"] == 0
    assert rec["applied"] is False
    assert "REVISIÓN MANUAL" in rec["alerts"][0]


def test_excess_fae_is_capped_to_invoice_and_applied_with_units_note():
    # Regla: la nota con más unidades que la factura se recorta en silencio
    # para el cálculo (se toma lo facturado y se sigue), con aviso
    # informativo en la vista previa. FAE=120 sobre 100 → exacta recortada.
    rec = _result(_historial({"fae": 120, "soles": -120}))
    assert rec["delta_soles"] == -120
    assert rec["applied"] is True
    assert rec["details"][0]["estado"] == "exacta"
    assert any("EXCESO EN UNIDADES" in a for a in rec["alerts"])
    assert any("APLICADA" in a for a in rec["alerts"])
    assert not any(a.startswith("AL13") for a in rec["alerts"])


def test_exact_physical_return_reduces_quantity_not_value():
    rec = _result(
        _historial(
            {"tipo": "NCR", "clase": "devolucion", "cantidad": -100, "fae": 0, "soles": -1000}
        )
    )
    assert rec["qty_return"] == 100
    assert rec["delta_soles"] == 0
    assert rec["applied"] is True


def test_partial_note_documents_are_evaluated_individually():
    # Cada nota se mide contra la factura original: dos parciales quedan
    # como puntuales sin aplicar (antes se bloqueaban en grupo).
    rec = _result(_historial({"fae": 50, "soles": -50}, {"fae": 50, "soles": -50}))
    assert rec["delta_soles"] == 0
    assert rec["applied"] is False
    assert "parcial" == rec["details"][0]["estado"]
    assert "parcial" == rec["details"][1]["estado"]


def test_consolidated_is_informational_even_when_use_nc_is_checked():
    rec = _result(_historial({"fae": 100, "soles": -100}), modality="consolidado")
    assert rec["delta_soles"] == 0
    assert rec["qty_return"] == 0
    assert rec["applied"] is False
    assert "EXACTA" in rec["alerts"][0]
    assert "no aplicado" in rec["alerts"][0]


def test_unchecked_use_does_not_adjust_but_keeps_visible_note():
    rec = _result(_historial({"fae": 100, "soles": -100}), docs=_policy(use_nc=False))
    assert rec["delta_soles"] == 0
    assert rec["details"][0]["mostrar"] is True
    assert rec["details"][0]["aplicada"] is False
    assert "check Usar desactivado" in rec["alerts"][0]


def test_hidden_note_is_still_audited_if_applied():
    docs = _policy()
    docs["nc"]["mostrar"] = False
    rec = _result(_historial({"fae": 100, "soles": -100}), docs=docs)
    assert rec["delta_soles"] == -100
    assert rec["details"][0]["mostrar"] is False
    # Applied adjustments remain traceable, even when historical display is off.
    assert rec["details"][0]["aplicada"] is True
    assert rec["alerts"] == []


def test_ndb_exact_fae_adjusts_price_as_signed_charge():
    rec = _result(_historial({"tipo": "NDB", "clase": "cargo", "fae": 100, "soles": 100}))
    assert rec["delta_soles"] == 100
    assert rec["qty_return"] == 0
    assert rec["applied"] is True


def test_same_invoice_number_and_sku_do_not_cross_clients():
    df = _historial({"fae": 100, "soles": -100})
    df["COD_CLIENTE"] = ["0001", "0001"]
    other_invoice = df.iloc[[0]].copy()
    other_invoice["COD_CLIENTE"] = "0002"
    other_note = df.iloc[[1]].copy()
    other_note["COD_CLIENTE"] = "0002"
    both = pd.concat([df, other_invoice, other_note], ignore_index=True)
    rec = reconciliar_notas(
        both,
        documentos={
            "facturas": [True, True],
            "nc": [True, True],
            "ndb": [True, False],
        },
    )
    assert ("0001", "F001-10", "123") in rec
    assert ("0002", "F001-10", "123") in rec
    assert rec[("0001", "F001-10", "123")]["delta_soles"] == -100
    assert rec[("0002", "F001-10", "123")]["delta_soles"] == -100


def test_two_exact_value_notes_both_apply_additively():
    # Regresión del bug: dos NC valor exactas sobre la misma factura deben
    # sumar (1.00 - 0.20 - 0.20 = 0.60), no bloquearse en grupo.
    rec = _result(_historial({"fae": 100, "soles": -20}, {"fae": 100, "soles": -20}))
    assert rec["delta_soles"] == -40
    assert rec["applied"] is True
    assert all(d["estado"] == "exacta" and d["aplicada"] for d in rec["details"])
    assert sum(1 for a in rec["alerts"] if "APLICADA" in a) == 2
    assert not any(a.startswith("AL13") for a in rec["alerts"])


def _historial_chico(*notas):
    """Factura 100 u @ S/1.00 (S/100) para probar el tope de valor."""
    df = _historial(*notas)
    df.loc[df["TIPO_CLASE"] == "factura", "SOLES"] = 100.0
    return df


def test_value_guard_blocks_only_the_note_that_exceeds_invoice_value():
    # 6 notas exactas de -20 sobre factura de S/100: las 5 primeras aplican
    # (saldo 0), la 6ª recibe AL13 fuerte y solo ella.
    notas = tuple({"fae": 100, "soles": -20} for _ in range(6))
    rec = _result(_historial_chico(*notas))
    assert rec["delta_soles"] == -100
    assert rec["applied"] is True
    aplicadas = [d for d in rec["details"] if d["aplicada"]]
    assert len(aplicadas) == 5
    assert rec["details"][-1]["estado"] == "exceso_valor"
    assert rec["details"][-1]["aplicada"] is False
    fuertes = [a for a in rec["alerts"] if a.startswith("AL13")]
    assert len(fuertes) == 1
    assert "EXCEDEN VALOR FACTURA" in fuertes[0]
    assert "saldo S/ 0.00" in fuertes[0]


def test_devolucion_exacta_reduce_cantidad_sin_tocar_precio():
    rec = _result(
        _historial({"tipo": "NCR", "clase": "devolucion", "cantidad": -100, "soles": -100})
    )
    assert rec["qty_return"] == 100
    assert rec["delta_soles"] == 0
    assert rec["applied"] is True


def test_second_exact_return_reports_no_balance_but_keeps_first():
    rec = _result(
        _historial(
            {"tipo": "NCR", "clase": "devolucion", "cantidad": -100, "soles": -100},
            {"tipo": "NCR", "clase": "devolucion", "cantidad": -100, "soles": -100},
        )
    )
    assert rec["qty_return"] == 100
    assert rec["details"][0]["estado"] == "exacta"
    assert rec["details"][0]["aplicada"] is True
    assert rec["details"][1]["estado"] == "exacta_sin_saldo"
    assert rec["details"][1]["aplicada"] is False
    assert any("SIN SALDO" in a for a in rec["alerts"])
    assert not any(a.startswith("AL13") for a in rec["alerts"])
