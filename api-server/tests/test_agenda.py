"""Tests — services/agenda.py

Couvre la détection de conflits (praticien/salle) et le calcul des
disponibilités. send_whatsapp_message tourne en mode dev (pas de
token configuré) donc ne fait aucun appel réseau ici.
"""
from datetime import date, datetime, timedelta

import pytest

from services.agenda import get_disponibilites, creer_rdv, annuler_rdv
from models.database import StatutRDV


@pytest.mark.asyncio
async def test_disponibilites_empty_on_weekend():
    # Samedi
    samedi = date(2026, 7, 25)
    assert samedi.weekday() == 5
    slots = await get_disponibilites(praticien_id=1, date_jour=samedi, duree_minutes=30, db=None, clinic_id=1)
    assert slots == []


@pytest.mark.asyncio
async def test_disponibilites_returns_slots_on_weekday(db, medecin):
    lundi = date(2026, 7, 20)
    assert lundi.weekday() == 0
    slots = await get_disponibilites(praticien_id=medecin.id, date_jour=lundi, duree_minutes=30, db=db, clinic_id=1)
    assert len(slots) > 0
    assert slots[0]["heure"] == "09:00"


@pytest.mark.asyncio
async def test_disponibilites_excludes_booked_slot(db, medecin, patient, acte):
    lundi = date(2026, 7, 20)
    debut = datetime.combine(lundi, datetime.min.time().replace(hour=10))
    rdv, _ = await creer_rdv(
        patient_id=patient.id, praticien_id=medecin.id, acte_id=acte.id,
        date_heure=debut, salle=None, db=db, clinic_id=1,
    )
    slots = await get_disponibilites(praticien_id=medecin.id, date_jour=lundi, duree_minutes=30, db=db, clinic_id=1)
    heures = [s["heure"] for s in slots]
    assert "10:00" not in heures


@pytest.mark.asyncio
async def test_creer_rdv_detects_praticien_conflict(db, medecin, patient, acte):
    debut = datetime(2026, 7, 20, 10, 0)
    await creer_rdv(patient_id=patient.id, praticien_id=medecin.id, acte_id=acte.id,
                     date_heure=debut, salle=None, db=db, clinic_id=1)

    with pytest.raises(ValueError, match="[Cc]onflit"):
        await creer_rdv(patient_id=patient.id, praticien_id=medecin.id, acte_id=acte.id,
                         date_heure=debut + timedelta(minutes=10), salle=None, db=db, clinic_id=1)


@pytest.mark.asyncio
async def test_creer_rdv_detects_salle_conflict_across_praticiens(db, medecin, assistante, patient, acte):
    debut = datetime(2026, 7, 20, 11, 0)
    await creer_rdv(patient_id=patient.id, praticien_id=medecin.id, acte_id=acte.id,
                     date_heure=debut, salle="Salle 1", db=db, clinic_id=1)

    with pytest.raises(ValueError, match="[Ss]alle"):
        await creer_rdv(patient_id=patient.id, praticien_id=assistante.id, acte_id=acte.id,
                         date_heure=debut + timedelta(minutes=5), salle="Salle 1", db=db, clinic_id=1)


@pytest.mark.asyncio
async def test_creer_rdv_allows_adjacent_non_overlapping_slots(db, medecin, patient, acte):
    debut1 = datetime(2026, 7, 20, 9, 0)
    rdv1, _ = await creer_rdv(patient_id=patient.id, praticien_id=medecin.id, acte_id=acte.id,
                               date_heure=debut1, salle=None, db=db, clinic_id=1)
    # acte dure 30 min -> le prochain à 9h30 ne doit pas être en conflit
    debut2 = debut1 + timedelta(minutes=30)
    rdv2, _ = await creer_rdv(patient_id=patient.id, praticien_id=medecin.id, acte_id=acte.id,
                               date_heure=debut2, salle=None, db=db, clinic_id=1)
    assert rdv1.id != rdv2.id


@pytest.mark.asyncio
async def test_creer_rdv_flags_missing_consent(db, medecin, patient, acte):
    _, consentement_manquant = await creer_rdv(
        patient_id=patient.id, praticien_id=medecin.id, acte_id=acte.id,
        date_heure=datetime(2026, 7, 20, 9, 0), salle=None, db=db, clinic_id=1,
    )
    assert consentement_manquant is True


@pytest.mark.asyncio
async def test_creer_rdv_no_missing_consent_flag_when_signed(db, medecin, patient, acte, consentement_valide):
    _, consentement_manquant = await creer_rdv(
        patient_id=patient.id, praticien_id=medecin.id, acte_id=acte.id,
        date_heure=datetime(2026, 7, 20, 9, 0), salle=None, db=db, clinic_id=1,
    )
    assert consentement_manquant is False


@pytest.mark.asyncio
async def test_creer_rdv_unknown_acte_raises(db, medecin, patient):
    with pytest.raises(ValueError, match="[Aa]cte"):
        await creer_rdv(patient_id=patient.id, praticien_id=medecin.id, acte_id=999999,
                         date_heure=datetime(2026, 7, 20, 9, 0), salle=None, db=db, clinic_id=1)


@pytest.mark.asyncio
async def test_annuler_rdv_sets_statut_annule(db, medecin, patient, acte):
    rdv, _ = await creer_rdv(patient_id=patient.id, praticien_id=medecin.id, acte_id=acte.id,
                              date_heure=datetime(2026, 7, 20, 9, 0), salle=None, db=db, clinic_id=1)
    annule = await annuler_rdv(rdv.id, raison="Patient indisponible", db=db, clinic_id=1)
    assert annule.statut == StatutRDV.ANNULE.value
    assert "Patient indisponible" in annule.notes_post_acte


@pytest.mark.asyncio
async def test_annuler_rdv_frees_the_slot_for_new_booking(db, medecin, patient, acte):
    debut = datetime(2026, 7, 20, 9, 0)
    rdv, _ = await creer_rdv(patient_id=patient.id, praticien_id=medecin.id, acte_id=acte.id,
                              date_heure=debut, salle=None, db=db, clinic_id=1)
    await annuler_rdv(rdv.id, raison="test", db=db, clinic_id=1)

    # Un nouveau RDV sur le même créneau ne doit plus être en conflit
    rdv2, _ = await creer_rdv(patient_id=patient.id, praticien_id=medecin.id, acte_id=acte.id,
                               date_heure=debut, salle=None, db=db, clinic_id=1)
    assert rdv2.id != rdv.id


@pytest.mark.asyncio
async def test_annuler_rdv_unknown_id_raises(db):
    with pytest.raises(ValueError, match="non trouvé"):
        await annuler_rdv(999999, raison="x", db=db, clinic_id=1)
