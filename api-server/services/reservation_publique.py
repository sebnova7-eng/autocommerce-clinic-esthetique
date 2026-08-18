"""
AutoCommerce Clinic — Réservation publique (landing page, sans auth)

Trouve ou crée le patient par téléphone, puis réutilise
services.agenda.creer_rdv (mêmes garde-fous : conflits praticien/salle,
détection consentement manquant).
"""
import re
from datetime import datetime

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from models.database import Patient, Utilisateur, RendezVous, ActeMedical, RoleEnum, StatutRDV
from services.agenda import creer_rdv, get_disponibilites
from services.clinic_settings import _resolve_clinic_id

TELEPHONE_REGEX = re.compile(r"^\+?[0-9]{8,15}$")


def _valider_telephone(telephone: str) -> str:
    telephone = telephone.strip().replace(" ", "")
    if not TELEPHONE_REGEX.match(telephone):
        raise ValueError("Numéro de téléphone invalide")
    return telephone


async def _find_or_create_patient(
    nom: str,
    prenom: str,
    telephone: str,
    db: AsyncSession,
    clinic_id: int | None = None,
) -> Patient:
    clinic_id = _resolve_clinic_id(clinic_id)
    result = await db.execute(
        select(Patient).where(
            Patient.telephone == telephone,
            Patient.clinic_id == clinic_id,
        )
    )
    patient = result.scalar_one_or_none()
    if patient:
        return patient

    patient = Patient(
        clinic_id=clinic_id, nom=nom.strip(), prenom=prenom.strip(), telephone=telephone,
        whatsapp_phone=telephone, source_acquisition="landing_page",
    )
    db.add(patient)
    await db.flush()
    return patient


async def _select_dynamic_practitioner(
    specialite: str | None,
    acte_id: int,
    date_heure: datetime,
    db: AsyncSession,
    clinic_id: int | None = None,
) -> Utilisateur:
    """Choisit un praticien actif, compatible et réellement libre sur le créneau."""
    clinic_id = _resolve_clinic_id(clinic_id)
    acte_result = await db.execute(
        select(ActeMedical).where(
            ActeMedical.id == acte_id,
            ActeMedical.clinic_id == clinic_id,
            ActeMedical.is_active,
        )
    )
    acte = acte_result.scalar_one_or_none()
    if not acte:
        raise ValueError("Acte non trouvé")

    query = select(Utilisateur).where(
        Utilisateur.is_active,
        Utilisateur.clinic_id == clinic_id,
        Utilisateur.role.in_([RoleEnum.MEDECIN.value, RoleEnum.ESTHETICIENNE.value]),
    )
    if specialite:
        query = query.where(func.lower(Utilisateur.specialite) == specialite.strip().lower())
    practitioners = (await db.execute(query.order_by(Utilisateur.id))).scalars().all()
    if not practitioners:
        raise ValueError("Aucun praticien actif ne correspond à la spécialité demandée")

    available = []
    for practitioner in practitioners:
        slots = await get_disponibilites(
            practitioner.id,
            date_heure.date(),
            acte.duree_minutes,
            db,
            clinic_id=clinic_id,
        )
        if any(slot["datetime"] == date_heure.isoformat() for slot in slots):
            load = await db.scalar(select(func.count(RendezVous.id)).where(and_(
                RendezVous.clinic_id == clinic_id,
                RendezVous.praticien_id == practitioner.id,
                RendezVous.date_heure_debut >= datetime.utcnow(),
                RendezVous.statut.in_([StatutRDV.PLANIFIE.value, StatutRDV.CONFIRME.value]),
            )))
            available.append((int(load or 0), practitioner.id, practitioner))
    if not available:
        raise ValueError("Aucun praticien disponible sur ce créneau")
    return min(available, key=lambda item: (item[0], item[1]))[2]


async def reserver_creneau_public(
    data: dict,
    db: AsyncSession,
    clinic_id: int | None = None,
) -> dict:
    clinic_id = _resolve_clinic_id(clinic_id)
    if not data.get("nom") or not data.get("prenom"):
        raise ValueError("Nom et prénom requis")

    telephone = _valider_telephone(data["telephone"])
    patient = await _find_or_create_patient(
        data["nom"], data["prenom"], telephone, db, clinic_id=clinic_id
    )
    praticien_id = data.get("praticien_id")
    if praticien_id is None:
        praticien = await _select_dynamic_practitioner(
            data.get("specialite"),
            data["acte_id"],
            data["date_heure"],
            db,
            clinic_id=clinic_id,
        )
        praticien_id = praticien.id

    rdv, consentement_manquant = await creer_rdv(
        patient_id=patient.id,
        praticien_id=praticien_id,
        acte_id=data["acte_id"],
        date_heure=data["date_heure"],
        salle=None,
        db=db,
        clinic_id=clinic_id,
    )

    return {
        "rdv_id": rdv.id,
        "patient_id": patient.id,
        "praticien_id": rdv.praticien_id,
        "statut": rdv.statut,
        "consentement_a_signer_sur_place": consentement_manquant,
    }
