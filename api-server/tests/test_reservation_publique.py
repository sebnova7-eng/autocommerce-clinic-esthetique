"""Tests — services/reservation_publique.py"""
from datetime import datetime

import pytest

from services.reservation_publique import reserver_creneau_public
from models.database import StatutRDV


@pytest.mark.asyncio
async def test_reservation_creates_new_patient(db, medecin, acte):
    result = await reserver_creneau_public({
        "nom": "Jelassi", "prenom": "Rania", "telephone": "+21622334455",
        "praticien_id": medecin.id, "acte_id": acte.id,
        "date_heure": datetime(2026, 7, 20, 10, 0),
    }, db)
    assert result["statut"] == StatutRDV.PLANIFIE.value
    assert result["consentement_a_signer_sur_place"] is True


@pytest.mark.asyncio
async def test_reservation_reuses_existing_patient_by_phone(db, medecin, acte, patient):
    result = await reserver_creneau_public({
        "nom": "Autre nom", "prenom": "Autre prenom", "telephone": patient.telephone,
        "praticien_id": medecin.id, "acte_id": acte.id,
        "date_heure": datetime(2026, 7, 20, 11, 0),
    }, db)
    assert result["patient_id"] == patient.id


@pytest.mark.asyncio
async def test_reservation_rejects_invalid_phone(db, medecin, acte):
    with pytest.raises(ValueError, match="téléphone invalide"):
        await reserver_creneau_public({
            "nom": "X", "prenom": "Y", "telephone": "abc",
            "praticien_id": medecin.id, "acte_id": acte.id,
            "date_heure": datetime(2026, 7, 20, 9, 0),
        }, db)


@pytest.mark.asyncio
async def test_reservation_rejects_missing_nom(db, medecin, acte):
    with pytest.raises(ValueError, match="prénom requis"):
        await reserver_creneau_public({
            "nom": "", "prenom": "Y", "telephone": "+21600000000",
            "praticien_id": medecin.id, "acte_id": acte.id,
            "date_heure": datetime(2026, 7, 20, 9, 0),
        }, db)


@pytest.mark.asyncio
async def test_reservation_respects_conflict_detection(db, medecin, acte):
    debut = datetime(2026, 7, 20, 14, 0)
    await reserver_creneau_public({
        "nom": "A", "prenom": "B", "telephone": "+21611112222",
        "praticien_id": medecin.id, "acte_id": acte.id, "date_heure": debut,
    }, db)

    with pytest.raises(ValueError, match="[Cc]onflit"):
        await reserver_creneau_public({
            "nom": "C", "prenom": "D", "telephone": "+21633334444",
            "praticien_id": medecin.id, "acte_id": acte.id, "date_heure": debut,
        }, db)
