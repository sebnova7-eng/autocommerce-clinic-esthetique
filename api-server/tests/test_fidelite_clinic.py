"""Tests — services/fidelite_clinic.py (tâches Celery précédemment cassées)"""
from datetime import date, datetime, timedelta

import pytest

from services.fidelite_clinic import check_anniversaire, check_inactivite, expire_points
from models.database import FideliteTransaction


@pytest.mark.asyncio
async def test_check_anniversaire_awards_points_once(db, patient):
    today = date.today()
    patient.date_naissance = today.replace(year=today.year - 30)
    patient.whatsapp_phone = "+21620000001"
    await db.flush()

    count = await check_anniversaire(db)
    assert count == 1
    await db.refresh(patient)
    assert patient.points_fidelite == 100

    # Deuxième appel le même jour : pas de double attribution
    count2 = await check_anniversaire(db)
    assert count2 == 0
    await db.refresh(patient)
    assert patient.points_fidelite == 100


@pytest.mark.asyncio
async def test_check_anniversaire_skips_other_dates(db, patient):
    patient.date_naissance = date(1990, 1, 1)
    await db.flush()
    # Ne plante pas et n'attribue rien si ce n'est pas l'anniversaire aujourd'hui
    if date.today().month != 1 or date.today().day != 1:
        count = await check_anniversaire(db)
        assert count == 0


@pytest.mark.asyncio
async def test_check_inactivite_targets_old_visits_only(db, patient):
    patient.derniere_visite = date.today() - timedelta(days=200)
    patient.whatsapp_phone = "+21620000002"
    await db.flush()

    count = await check_inactivite(db)
    assert count == 1


@pytest.mark.asyncio
async def test_check_inactivite_skips_recent_visits(db, patient):
    patient.derniere_visite = date.today() - timedelta(days=5)
    patient.whatsapp_phone = "+21620000003"
    await db.flush()

    count = await check_inactivite(db)
    assert count == 0


@pytest.mark.asyncio
async def test_expire_points_clears_old_inactive_balance(db, patient):
    patient.points_fidelite = 250
    await db.flush()
    old_tx = FideliteTransaction(
        clinic_id=1, patient_id=patient.id, type="gain", points=250,
        solde_apres=250, motif="ancien gain",
        created_at=datetime.utcnow() - timedelta(days=400),
    )
    db.add(old_tx)
    await db.flush()

    count = await expire_points(db)
    assert count == 1
    await db.refresh(patient)
    assert patient.points_fidelite == 0


@pytest.mark.asyncio
async def test_expire_points_keeps_recent_activity(db, patient):
    patient.points_fidelite = 80
    await db.flush()
    recent_tx = FideliteTransaction(
        clinic_id=1, patient_id=patient.id, type="gain", points=80,
        solde_apres=80, motif="gain récent",
        created_at=datetime.utcnow() - timedelta(days=10),
    )
    db.add(recent_tx)
    await db.flush()

    count = await expire_points(db)
    assert count == 0
    await db.refresh(patient)
    assert patient.points_fidelite == 80
