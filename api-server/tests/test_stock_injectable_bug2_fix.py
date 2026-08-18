"""Tests de régression — correctif Bug #2.

Le point critique est d'accepter un enregistrement d'utilisation via
``lot_id`` déjà résolu côté frontend, sans redécoder le QR / barcode au
moment du POST final.
"""

from decimal import Decimal

import pytest
from pydantic import ValidationError

import api.v1.stock_injectable as stock_router



def test_usage_request_requires_code_or_lot_id():
    with pytest.raises(ValidationError, match="code soit lot_id|code ou lot_id"):
        stock_router.UsageRequest(
            patient_id=1,
            praticien_id=2,
            quantite=Decimal("1.00"),
            unite="unite",
        )



def test_usage_request_accepts_lot_id_without_code():
    payload = stock_router.UsageRequest(
        lot_id=123,
        patient_id=1,
        praticien_id=2,
        quantite=Decimal("1.00"),
        unite="unite",
    )

    assert payload.lot_id == 123
    assert payload.code is None


@pytest.mark.asyncio
async def test_register_lot_usage_with_lot_id_skips_decode_scan(db, lot, patient, medecin, monkeypatch):
    def forbidden_decode_scan(_code: str):
        raise AssertionError("decode_scan ne doit pas être appelé quand lot_id est fourni")

    monkeypatch.setattr(stock_router, "decode_scan", forbidden_decode_scan)

    payload = stock_router.UsageRequest(
        lot_id=lot.id,
        patient_id=patient.id,
        praticien_id=medecin.id,
        quantite=Decimal("1.00"),
        unite="unite",
        type_injection="Botox",
    )

    result = await stock_router.register_lot_usage(
        data=payload,
        db=db,
        current_user={"role": medecin.role},
    )

    await db.refresh(lot)

    assert result["lot_id"] == lot.id
    assert result["quantite_utilisee"] == 1.0
    assert lot.quantite_restante == Decimal("99.00")
