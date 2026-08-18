"""Tests — services/fidelite.py"""
import pytest

from services.fidelite import add_points, redeem_points, get_historique, get_overview
from models.database import NiveauFidelite


@pytest.mark.asyncio
async def test_get_overview_aggregates_across_patients(db, patient):
    await add_points(patient.id, 150, "Gain test", db)
    overview = await get_overview(db)
    assert overview["total_points"] == 150
    assert len(overview["transactions"]) == 1
    assert overview["transactions"][0]["patient_nom"] == f"{patient.prenom} {patient.nom}"


@pytest.mark.asyncio
async def test_add_points_increases_balance(db, patient):
    tx = await add_points(patient.id, 100, "Test gain", db)
    assert tx.solde_apres == 100
    await db.refresh(patient)
    assert patient.points_fidelite == 100


@pytest.mark.asyncio
async def test_add_points_upgrades_niveau(db, patient):
    await add_points(patient.id, 2500, "Gros achat", db)
    await db.refresh(patient)
    assert patient.niveau_fidelite == NiveauFidelite.GOLD.value


@pytest.mark.asyncio
async def test_redeem_points_decreases_balance(db, patient):
    await add_points(patient.id, 200, "gain", db)
    tx = await redeem_points(patient.id, 50, "Réduction", db)
    assert tx.solde_apres == 150


@pytest.mark.asyncio
async def test_redeem_points_rejects_insufficient_balance(db, patient):
    await add_points(patient.id, 10, "gain", db)
    with pytest.raises(ValueError, match="insuffisant"):
        await redeem_points(patient.id, 100, "trop", db)


@pytest.mark.asyncio
async def test_redeem_points_can_downgrade_niveau(db, patient):
    await add_points(patient.id, 2500, "gain", db)
    await redeem_points(patient.id, 2400, "depense", db)
    await db.refresh(patient)
    assert patient.niveau_fidelite == NiveauFidelite.BRONZE.value


@pytest.mark.asyncio
async def test_historique_orders_most_recent_first(db, patient):
    await add_points(patient.id, 10, "premier", db)
    await add_points(patient.id, 20, "deuxieme", db)
    historique = await get_historique(patient.id, db)
    assert historique[0].motif == "deuxieme"


@pytest.mark.asyncio
async def test_add_points_unknown_patient_raises(db):
    with pytest.raises(ValueError, match="non trouvé"):
        await add_points(999999, 10, "x", db)
