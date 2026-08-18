"""Workflow sécurisé Public Gateway -> BookingRequest -> Appointment."""
from __future__ import annotations

from datetime import datetime
from hashlib import sha256

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.database import ActeMedical, BookingRequest, Utilisateur
from services.agenda import creer_rdv
from services.reservation_publique import _find_or_create_patient, _select_dynamic_practitioner, _valider_telephone


async def submit_booking_request(
    data: dict,
    db: AsyncSession,
    *,
    clinic_id: int,
) -> dict:
    nom = str(data.get("nom") or "").strip()
    prenom = str(data.get("prenom") or "").strip()
    if not nom or not prenom:
        raise ValueError("Nom et prénom requis")

    telephone = _valider_telephone(str(data.get("telephone") or ""))
    acte_id = int(data["acte_id"])
    date_heure = data["date_heure"]
    if isinstance(date_heure, str):
        date_heure = datetime.fromisoformat(date_heure)

    acte = await db.scalar(
        select(ActeMedical).where(
            ActeMedical.id == acte_id,
            ActeMedical.clinic_id == clinic_id,
            ActeMedical.is_active,
        )
    )
    if not acte:
        raise ValueError("Acte non trouvé")

    praticien_id = data.get("praticien_id")
    if praticien_id is not None:
        praticien_id = int(praticien_id)
        practitioner = await db.scalar(
            select(Utilisateur).where(
                Utilisateur.id == praticien_id,
                Utilisateur.clinic_id == clinic_id,
                Utilisateur.is_active,
            )
        )
        if not practitioner:
            raise ValueError("Praticien non trouvé")

    fingerprint_source = "|".join(
        [
            nom.casefold(),
            prenom.casefold(),
            telephone,
            str(praticien_id or ""),
            str(acte_id),
            date_heure.isoformat(),
        ]
    )
    fingerprint = sha256(fingerprint_source.encode("utf-8")).hexdigest()
    existing = await db.scalar(
        select(BookingRequest).where(
            BookingRequest.clinic_id == clinic_id,
            BookingRequest.request_fingerprint == fingerprint,
        )
    )
    if existing:
        return {
            "booking_request_id": existing.id,
            "statut": existing.statut,
            "duplicate": True,
        }

    request = BookingRequest(
        clinic_id=clinic_id,
        nom=nom,
        prenom=prenom,
        telephone=telephone,
        email=data.get("email"),
        praticien_id=praticien_id,
        acte_id=acte_id,
        date_heure=date_heure,
        request_fingerprint=fingerprint,
    )
    db.add(request)
    await db.flush()
    return {
        "booking_request_id": request.id,
        "statut": request.statut,
        "duplicate": False,
    }


async def approve_booking_request(
    booking_request_id: int,
    db: AsyncSession,
    *,
    clinic_id: int,
    reviewer_id: int,
) -> dict:
    request = await db.scalar(
        select(BookingRequest).where(
            BookingRequest.id == booking_request_id,
            BookingRequest.clinic_id == clinic_id,
        )
    )
    if not request:
        raise ValueError("BookingRequest non trouvée")
    if request.statut == "accepted" and request.rendez_vous_id:
        return {"booking_request_id": request.id, "statut": request.statut, "rendez_vous_id": request.rendez_vous_id}
    if request.statut != "pending":
        raise ValueError("BookingRequest déjà traitée")

    patient = await _find_or_create_patient(
        request.nom, request.prenom, request.telephone, db, clinic_id=clinic_id
    )
    if request.email and not patient.email:
        patient.email = request.email

    praticien_id = request.praticien_id
    if praticien_id is None:
        practitioner = await _select_dynamic_practitioner(
            None, request.acte_id, request.date_heure, db, clinic_id=clinic_id
        )
        praticien_id = practitioner.id

    rdv, consent_missing = await creer_rdv(
        patient_id=patient.id,
        praticien_id=praticien_id,
        acte_id=request.acte_id,
        date_heure=request.date_heure,
        salle=None,
        db=db,
        created_by=reviewer_id,
        clinic_id=clinic_id,
    )
    request.patient_id = patient.id
    request.rendez_vous_id = rdv.id
    request.reviewed_by = reviewer_id
    request.statut = "accepted"
    await db.flush()
    return {
        "booking_request_id": request.id,
        "statut": request.statut,
        "rendez_vous_id": rdv.id,
        "patient_id": patient.id,
        "consentement_a_signer_sur_place": consent_missing,
    }


async def reject_booking_request(
    booking_request_id: int,
    db: AsyncSession,
    *,
    clinic_id: int,
    reviewer_id: int,
    notes: str | None = None,
) -> dict:
    request = await db.scalar(
        select(BookingRequest).where(
            BookingRequest.id == booking_request_id,
            BookingRequest.clinic_id == clinic_id,
        )
    )
    if not request:
        raise ValueError("BookingRequest non trouvée")
    if request.statut != "pending":
        raise ValueError("BookingRequest déjà traitée")
    request.statut = "rejected"
    request.reviewed_by = reviewer_id
    request.review_notes = (notes or "")[:500] or None
    await db.flush()
    return {"booking_request_id": request.id, "statut": request.statut}
