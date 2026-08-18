"""Tests — services/stock_injectable.py

Couvre le débit de stock, les refus (stock insuffisant, lot expiré,
lot épuisé) et le classement des alertes (rouge/orange/vert).
"""
from datetime import date, timedelta
from decimal import Decimal

import pytest

from services.stock_injectable import register_usage, check_stock_alerts
from models.database import LotInjectable, StatutLot


@pytest.mark.asyncio
async def test_register_usage_debits_stock(db, lot, patient, medecin):
    util = await register_usage(
        lot_id=lot.id, dossier_id=None, patient_id=patient.id,
        praticien_id=medecin.id, quantite=Decimal("10.00"), unite="unite", db=db,
    )
    await db.refresh(lot)
    assert lot.quantite_restante == Decimal("90.00")
    assert util.quantite_utilisee == Decimal("10.00")


@pytest.mark.asyncio
async def test_register_usage_rejects_insufficient_stock(db, lot, patient, medecin):
    with pytest.raises(ValueError, match="[Ss]tock insuffisant"):
        await register_usage(
            lot_id=lot.id, dossier_id=None, patient_id=patient.id,
            praticien_id=medecin.id, quantite=Decimal("1000.00"), unite="unite", db=db,
        )


@pytest.mark.asyncio
async def test_register_usage_rejects_expired_lot(db, produit, patient, medecin):
    expired_lot = LotInjectable(
        clinic_id=1, produit_id=produit.id, numero_lot="LOT-EXPIRED",
        date_expiration=date.today() - timedelta(days=1),
        quantite_initiale=Decimal("50.00"), quantite_restante=Decimal("50.00"),
        statut=StatutLot.DISPONIBLE.value,
    )
    db.add(expired_lot)
    await db.flush()

    with pytest.raises(ValueError, match="[Ee]xpir"):
        await register_usage(
            lot_id=expired_lot.id, dossier_id=None, patient_id=patient.id,
            praticien_id=medecin.id, quantite=Decimal("1.00"), unite="unite", db=db,
        )
    assert expired_lot.statut == StatutLot.EXPIRE.value


@pytest.mark.asyncio
async def test_register_usage_rejects_already_exhausted_lot(db, produit, patient, medecin):
    exhausted = LotInjectable(
        clinic_id=1, produit_id=produit.id, numero_lot="LOT-EMPTY",
        date_expiration=date.today() + timedelta(days=30),
        quantite_initiale=Decimal("50.00"), quantite_restante=Decimal("0.00"),
        statut=StatutLot.EPUISE.value,
    )
    db.add(exhausted)
    await db.flush()

    with pytest.raises(ValueError, match="indisponible"):
        await register_usage(
            lot_id=exhausted.id, dossier_id=None, patient_id=patient.id,
            praticien_id=medecin.id, quantite=Decimal("1.00"), unite="unite", db=db,
        )


@pytest.mark.asyncio
async def test_register_usage_marks_lot_epuise_when_fully_consumed(db, lot, patient, medecin):
    await register_usage(
        lot_id=lot.id, dossier_id=None, patient_id=patient.id,
        praticien_id=medecin.id, quantite=Decimal("100.00"), unite="unite", db=db,
    )
    await db.refresh(lot)
    assert lot.statut == StatutLot.EPUISE.value
    assert lot.quantite_restante == Decimal("0.00")


@pytest.mark.asyncio
async def test_register_usage_marks_lot_quarantaine_below_minimum(db, lot, patient, medecin, produit):
    # stock_minimum=10 (fixture produit) ; on laisse 5 restants
    await register_usage(
        lot_id=lot.id, dossier_id=None, patient_id=patient.id,
        praticien_id=medecin.id, quantite=Decimal("95.00"), unite="unite", db=db,
    )
    await db.refresh(lot)
    assert lot.quantite_restante == Decimal("5.00")
    assert lot.statut == StatutLot.QUARANTAINE.value


@pytest.mark.asyncio
async def test_register_usage_unknown_lot_raises(db, patient, medecin):
    with pytest.raises(ValueError, match="non trouvé"):
        await register_usage(
            lot_id=999999, dossier_id=None, patient_id=patient.id,
            praticien_id=medecin.id, quantite=Decimal("1.00"), unite="unite", db=db,
        )


# ── Alertes stock ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_alert_rouge_for_expired_lot(db, produit):
    expired = LotInjectable(
        clinic_id=1, produit_id=produit.id, numero_lot="LOT-R",
        date_expiration=date.today() - timedelta(days=5),
        quantite_initiale=Decimal("30.00"), quantite_restante=Decimal("30.00"),
        statut=StatutLot.DISPONIBLE.value,
    )
    db.add(expired)
    await db.flush()

    alerts = await check_stock_alerts(db)
    assert any(a.niveau == "rouge" and a.numero_lot == "LOT-R" for a in alerts)


@pytest.mark.asyncio
async def test_alert_rouge_for_zero_stock(db, produit):
    empty = LotInjectable(
        clinic_id=1, produit_id=produit.id, numero_lot="LOT-Z",
        date_expiration=date.today() + timedelta(days=100),
        quantite_initiale=Decimal("10.00"), quantite_restante=Decimal("0.00"),
        statut=StatutLot.QUARANTAINE.value,
    )
    db.add(empty)
    await db.flush()

    alerts = await check_stock_alerts(db)
    assert any(a.niveau == "rouge" and a.numero_lot == "LOT-Z" for a in alerts)


@pytest.mark.asyncio
async def test_alert_orange_for_expiring_soon(db, produit):
    soon = LotInjectable(
        clinic_id=1, produit_id=produit.id, numero_lot="LOT-O",
        date_expiration=date.today() + timedelta(days=15),
        quantite_initiale=Decimal("30.00"), quantite_restante=Decimal("30.00"),
        statut=StatutLot.DISPONIBLE.value,
    )
    db.add(soon)
    await db.flush()

    alerts = await check_stock_alerts(db)
    assert any(a.niveau == "orange" and a.numero_lot == "LOT-O" for a in alerts)


@pytest.mark.asyncio
async def test_alert_vert_for_expiring_within_60_days(db, produit):
    info = LotInjectable(
        clinic_id=1, produit_id=produit.id, numero_lot="LOT-V",
        date_expiration=date.today() + timedelta(days=45),
        quantite_initiale=Decimal("30.00"), quantite_restante=Decimal("30.00"),
        statut=StatutLot.DISPONIBLE.value,
    )
    db.add(info)
    await db.flush()

    alerts = await check_stock_alerts(db)
    assert any(a.niveau == "vert" and a.numero_lot == "LOT-V" for a in alerts)


@pytest.mark.asyncio
async def test_no_alert_for_healthy_lot(db, lot):
    """Le lot par défaut (180j, stock plein) ne doit déclencher aucune alerte."""
    alerts = await check_stock_alerts(db)
    assert not any(a.numero_lot == lot.numero_lot for a in alerts)
