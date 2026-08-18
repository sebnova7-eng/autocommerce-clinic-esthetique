from datetime import datetime, timedelta

import pytest
from sqlalchemy import select

from models.database import BookingRequest, Patient, RendezVous
from services.booking_requests import (
    approve_booking_request,
    reject_booking_request,
    submit_booking_request,
)


@pytest.mark.asyncio
async def test_public_submission_is_pending_and_deduplicated(db, acte, medecin):
    payload = {
        "nom": "Demande",
        "prenom": "Publique",
        "telephone": "+21620000999",
        "email": "booking@example.com",
        "praticien_id": medecin.id,
        "acte_id": acte.id,
        "date_heure": datetime.utcnow() + timedelta(days=2),
    }

    first = await submit_booking_request(payload, db, clinic_id=1)
    duplicate = await submit_booking_request(payload, db, clinic_id=1)

    assert first["statut"] == "pending"
    assert first["duplicate"] is False
    assert duplicate["duplicate"] is True
    assert duplicate["booking_request_id"] == first["booking_request_id"]
    assert await db.scalar(select(Patient).where(Patient.telephone == payload["telephone"])) is None


@pytest.mark.asyncio
async def test_approval_creates_patient_and_appointment_in_same_clinic(db, acte, medecin, assistante):
    payload = {
        "nom": "Validation",
        "prenom": "Interne",
        "telephone": "+21620000888",
        "acte_id": acte.id,
        "praticien_id": medecin.id,
        "date_heure": datetime.utcnow() + timedelta(days=3),
    }
    submitted = await submit_booking_request(payload, db, clinic_id=1)
    approved = await approve_booking_request(
        submitted["booking_request_id"],
        db,
        clinic_id=1,
        reviewer_id=assistante.id,
    )

    assert approved["statut"] == "accepted"
    assert approved["patient_id"]
    assert approved["rendez_vous_id"]
    request = await db.get(BookingRequest, submitted["booking_request_id"])
    appointment = await db.get(RendezVous, approved["rendez_vous_id"])
    patient = await db.get(Patient, approved["patient_id"])
    assert request.clinic_id == appointment.clinic_id == patient.clinic_id == 1


@pytest.mark.asyncio
async def test_rejection_does_not_create_patient_or_appointment(db, acte, medecin, assistante):
    payload = {
        "nom": "Refus",
        "prenom": "Public",
        "telephone": "+21620000777",
        "acte_id": acte.id,
        "praticien_id": medecin.id,
        "date_heure": datetime.utcnow() + timedelta(days=4),
    }
    submitted = await submit_booking_request(payload, db, clinic_id=1)
    rejected = await reject_booking_request(
        submitted["booking_request_id"],
        db,
        clinic_id=1,
        reviewer_id=assistante.id,
        notes="Créneau indisponible",
    )

    assert rejected["statut"] == "rejected"
    assert await db.scalar(select(Patient).where(Patient.telephone == payload["telephone"])) is None
    assert await db.scalar(select(RendezVous).where(RendezVous.patient_id.is_(None))) is None
