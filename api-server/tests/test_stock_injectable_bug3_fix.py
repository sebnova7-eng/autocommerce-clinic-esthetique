"""Tests de non-régression — Bug #3 (date_injection optionnelle).

Le service doit toujours renseigner ``date_utilisation`` :
- fallback automatique à ``datetime.utcnow()`` si ``date_injection`` est absente ;
- conservation exacte de la date fournie si elle est explicitement transmise.
"""

from datetime import datetime, timedelta
from decimal import Decimal

import pytest

from services.stock_injectable import register_usage


@pytest.mark.asyncio
async def test_register_usage_defaults_date_utilisation_to_utc_now(db, lot, patient, medecin):
    before = datetime.utcnow() - timedelta(seconds=1)

    utilisation = await register_usage(
        lot_id=lot.id,
        dossier_id=None,
        patient_id=patient.id,
        praticien_id=medecin.id,
        quantite=Decimal("1.00"),
        unite="unite",
        db=db,
        date_injection=None,
    )

    after = datetime.utcnow() + timedelta(seconds=1)

    assert utilisation.date_utilisation is not None
    assert before <= utilisation.date_utilisation <= after


@pytest.mark.asyncio
async def test_register_usage_preserves_explicit_date_injection(db, lot, patient, medecin):
    explicit_date = datetime(2026, 1, 15, 14, 30, 45)

    utilisation = await register_usage(
        lot_id=lot.id,
        dossier_id=None,
        patient_id=patient.id,
        praticien_id=medecin.id,
        quantite=Decimal("1.00"),
        unite="unite",
        db=db,
        date_injection=explicit_date,
    )

    assert utilisation.date_utilisation == explicit_date
