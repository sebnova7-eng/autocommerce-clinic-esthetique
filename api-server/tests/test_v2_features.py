from datetime import datetime, timedelta

import pytest

from models.database import RendezVous, StatutRDV, Utilisateur, RoleEnum
from services.dashboard_ia import DashboardIAService
from services.reservation_publique import reserver_creneau_public


@pytest.mark.asyncio
async def test_cancellation_risk_uses_real_history(db, patient, acte, medecin):
    now = datetime.utcnow()
    db.add_all([
        RendezVous(
            clinic_id=1, patient_id=patient.id, praticien_id=medecin.id,
            acte_id=acte.id, date_heure_debut=now - timedelta(days=10),
            date_heure_fin=now - timedelta(days=10) + timedelta(minutes=30),
            statut=StatutRDV.ANNULE.value,
        ),
        RendezVous(
            clinic_id=1, patient_id=patient.id, praticien_id=medecin.id,
            acte_id=acte.id, date_heure_debut=now + timedelta(days=2),
            date_heure_fin=now + timedelta(days=2, minutes=30),
            statut=StatutRDV.PLANIFIE.value,
        ),
    ])
    await db.flush()

    result = await DashboardIAService.get_cancellation_risk(db, clinic_id=1)

    assert result["historical_appointments"] == 1
    assert result["historical_cancellations_or_no_shows"] == 1
    assert result["appointments"][0]["risk_score"] == pytest.approx(2 / 3, abs=0.0001)
    assert result["data_source"].startswith("rendez_vous")


@pytest.mark.asyncio
async def test_dynamic_booking_routes_to_available_specialist(db, patient, acte, medecin):
    medecin.specialite = "Injection"
    other = Utilisateur(
        clinic_id=1, email="other@clinic.tn", hashed_password="x", nom="Second",
        prenom="Lea", role=RoleEnum.MEDECIN.value, specialite="Injection",
    )
    db.add(other)
    await db.flush()
    # Trouver le prochain jour ouvrable (lundi=0 à vendredi=4)
    requested = datetime.utcnow().replace(hour=10, minute=0, second=0, microsecond=0) + timedelta(days=1)
    while requested.weekday() >= 5:
        requested += timedelta(days=1)

    result = await reserver_creneau_public({
        "nom": "Nouveau", "prenom": "Patient", "telephone": "+21621111111",
        "specialite": "Injection", "acte_id": acte.id, "date_heure": requested,
    }, db)

    assert result["praticien_id"] in {medecin.id, other.id}
    assert result["rdv_id"] is not None


@pytest.mark.asyncio
async def test_explicit_practitioner_booking_contract_is_preserved(db, acte, medecin):
    requested = datetime.utcnow().replace(hour=11, minute=0, second=0, microsecond=0) + timedelta(days=1)
    result = await reserver_creneau_public({
        "nom": "Existant", "prenom": "Patient", "telephone": "+21622222222",
        "praticien_id": medecin.id, "acte_id": acte.id, "date_heure": requested,
    }, db)

    assert result["praticien_id"] == medecin.id
    assert result["statut"] == StatutRDV.PLANIFIE.value
