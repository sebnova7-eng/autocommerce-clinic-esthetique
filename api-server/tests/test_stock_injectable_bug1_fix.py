"""Tests de non-régression — Bug #1 (audit) : register_usage()

Ces tests couvrent spécifiquement les failles identifiées dans l'audit :
1. Décrémentation exacte au plein-lot (quantite == quantite_restante).
2. Rejet strict d'une quantité nulle ou négative.
3. Cast Decimal robuste (float, str, Decimal) sans perte de précision.
4. Rejet d'un second appel lorsque le stock est déjà à zéro.
5. Décrémentation cumulée sur plusieurs appels successifs.
6. Cohérence transactionnelle : aucune UtilisationLot ne doit exister
   si la décrémentation est refusée.
"""
from datetime import date, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import select

from services.stock_injectable import register_usage
from models.database import LotInjectable, UtilisationLot, StatutLot


# ── Cas nominal exact ────────────────────────────────────────────

@pytest.mark.asyncio
async def test_bug1_full_consumption_marks_epuise_and_zero(db, lot, patient, medecin):
    """quantite == quantite_restante : stock passe à 0.00 et statut EPUISE."""
    initial = Decimal(str(lot.quantite_restante))
    await register_usage(
        lot_id=lot.id, dossier_id=None, patient_id=patient.id,
        praticien_id=medecin.id, quantite=initial, unite="unite", db=db,
    )
    await db.refresh(lot)
    assert lot.quantite_restante == Decimal("0.00")
    assert lot.statut == StatutLot.EPUISE.value


@pytest.mark.asyncio
async def test_bug1_second_call_on_exhausted_lot_raises(db, lot, patient, medecin):
    """Après avoir vidé un lot, un second appel doit lever ValueError."""
    initial = Decimal(str(lot.quantite_restante))
    await register_usage(
        lot_id=lot.id, dossier_id=None, patient_id=patient.id,
        praticien_id=medecin.id, quantite=initial, unite="unite", db=db,
    )
    with pytest.raises(ValueError, match="indisponible|insuffisant"):
        await register_usage(
            lot_id=lot.id, dossier_id=None, patient_id=patient.id,
            praticien_id=medecin.id, quantite=Decimal("0.50"), unite="unite", db=db,
        )


# ── Validation des entrées ────────────────────────────────────────

@pytest.mark.asyncio
async def test_bug1_zero_quantity_rejected(db, lot, patient, medecin):
    with pytest.raises(ValueError, match="strictement positive"):
        await register_usage(
            lot_id=lot.id, dossier_id=None, patient_id=patient.id,
            praticien_id=medecin.id, quantite=Decimal("0"), unite="unite", db=db,
        )


@pytest.mark.asyncio
async def test_bug1_negative_quantity_rejected(db, lot, patient, medecin):
    with pytest.raises(ValueError, match="strictement positive"):
        await register_usage(
            lot_id=lot.id, dossier_id=None, patient_id=patient.id,
            praticien_id=medecin.id, quantite=Decimal("-1.00"), unite="unite", db=db,
        )


@pytest.mark.asyncio
async def test_bug1_accepts_float_and_str_quantity(db, lot, patient, medecin):
    """Le service doit caster proprement float/str vers Decimal."""
    initial = Decimal(str(lot.quantite_restante))

    # float → Decimal
    await register_usage(
        lot_id=lot.id, dossier_id=None, patient_id=patient.id,
        praticien_id=medecin.id, quantite=0.5, unite="unite", db=db,  # type: ignore[arg-type]
    )
    await db.refresh(lot)
    assert lot.quantite_restante == initial - Decimal("0.5")

    # str → Decimal
    await register_usage(
        lot_id=lot.id, dossier_id=None, patient_id=patient.id,
        praticien_id=medecin.id, quantite="0.25", unite="unite", db=db,  # type: ignore[arg-type]
    )
    await db.refresh(lot)
    assert lot.quantite_restante == initial - Decimal("0.75")


# ── Décrémentation cumulée ────────────────────────────────────────

@pytest.mark.asyncio
async def test_bug1_multiple_calls_cumulative_decrement(db, lot, patient, medecin):
    """Trois appels de 10.00 doivent laisser initial - 30.00."""
    initial = Decimal(str(lot.quantite_restante))
    for _ in range(3):
        await register_usage(
            lot_id=lot.id, dossier_id=None, patient_id=patient.id,
            praticien_id=medecin.id, quantite=Decimal("10.00"), unite="unite", db=db,
        )
    await db.refresh(lot)
    assert lot.quantite_restante == initial - Decimal("30.00")


# ── Cohérence transactionnelle ────────────────────────────────────

@pytest.mark.asyncio
async def test_bug1_no_orphan_utilisation_when_stock_insufficient(db, lot, patient, medecin):
    """Si register_usage échoue pour stock insuffisant, aucun UtilisationLot
    ne doit avoir été créé pour ce lot."""
    before = await db.execute(
        select(UtilisationLot).where(UtilisationLot.lot_id == lot.id)
    )
    count_before = len(before.all())

    with pytest.raises(ValueError, match="insuffisant"):
        await register_usage(
            lot_id=lot.id, dossier_id=None, patient_id=patient.id,
            praticien_id=medecin.id, quantite=Decimal("999999.00"),
            unite="unite", db=db,
        )

    after = await db.execute(
        select(UtilisationLot).where(UtilisationLot.lot_id == lot.id)
    )
    count_after = len(after.all())
    assert count_after == count_before, "Aucune utilisation ne doit être créée si le débit échoue"


@pytest.mark.asyncio
async def test_bug1_no_orphan_utilisation_when_zero_quantity(db, lot, patient, medecin):
    """Une quantité nulle refusée ne doit créer aucune UtilisationLot."""
    with pytest.raises(ValueError):
        await register_usage(
            lot_id=lot.id, dossier_id=None, patient_id=patient.id,
            praticien_id=medecin.id, quantite=Decimal("0"), unite="unite", db=db,
        )

    result = await db.execute(
        select(UtilisationLot)
        .where(UtilisationLot.lot_id == lot.id)
        .where(UtilisationLot.quantite_utilisee == Decimal("0"))
    )
    assert result.first() is None


# ── Décimales fines (précision) ───────────────────────────────────

@pytest.mark.asyncio
async def test_bug1_fine_grained_decimal_precision(db, produit, patient, medecin):
    """Un lot à 1.00 mL, deux appels de 0.5 mL, doit atterrir exactement à 0."""
    fine_lot = LotInjectable(
        clinic_id=1, produit_id=produit.id, numero_lot="LOT-FINE",
        date_expiration=date.today() + timedelta(days=90),
        quantite_initiale=Decimal("1.00"),
        quantite_restante=Decimal("1.00"),
        statut=StatutLot.DISPONIBLE.value,
    )
    db.add(fine_lot)
    await db.flush()

    await register_usage(
        lot_id=fine_lot.id, dossier_id=None, patient_id=patient.id,
        praticien_id=medecin.id, quantite=Decimal("0.50"), unite="mL", db=db,
    )
    await db.refresh(fine_lot)
    assert fine_lot.quantite_restante == Decimal("0.50")

    await register_usage(
        lot_id=fine_lot.id, dossier_id=None, patient_id=patient.id,
        praticien_id=medecin.id, quantite=Decimal("0.50"), unite="mL", db=db,
    )
    await db.refresh(fine_lot)
    assert fine_lot.quantite_restante == Decimal("0.00")
    assert fine_lot.statut == StatutLot.EPUISE.value

    # Un 3ᵉ appel de 0.50 doit être rejeté
    with pytest.raises(ValueError, match="indisponible|insuffisant"):
        await register_usage(
            lot_id=fine_lot.id, dossier_id=None, patient_id=patient.id,
            praticien_id=medecin.id, quantite=Decimal("0.50"), unite="mL", db=db,
        )
