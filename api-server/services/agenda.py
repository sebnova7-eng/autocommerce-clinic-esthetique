"""
AutoCommerce Clinic — Gestion agenda
Disponibilités, création RDV, rappels WhatsApp
"""

import logging
from datetime import datetime, timedelta, date
from typing import List, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

logger = logging.getLogger(__name__)

from models.database import (
    RendezVous, Patient, Utilisateur, ActeMedical,
    StatutRDV,
)
from services.consentement import verify_consent
from services.clinic_settings import _resolve_clinic_id
from services.whatsapp_service import send_whatsapp_message
from services.branding import get_branding_context
from config import WA_TEMPLATES


async def get_disponibilites(
    praticien_id: int,
    date_jour: date,
    duree_minutes: int,
    db: AsyncSession,
    clinic_id: Optional[int] = None,
) -> List[dict]:
    """Retourne les créneaux libres d'un praticien pour une date.

    Exclut RDV existants + blocages.
    Horaires : 9h-18h (lun-jeu), 9h-13h (ven).
    """
    clinic_id = _resolve_clinic_id(clinic_id)

    # Déterminer les horaires selon le jour
    jour_semaine = date_jour.weekday()  # 0=lundi, 6=dimanche
    if jour_semaine >= 5:  # weekend
        return []

    heure_debut = 9
    heure_fin = 18 if jour_semaine < 4 else 13

    # Créneaux de base (toutes les 30 min)
    creneaux = []
    current = datetime.combine(date_jour, datetime.min.time().replace(hour=heure_debut))
    end = datetime.combine(date_jour, datetime.min.time().replace(hour=heure_fin))

    while current + timedelta(minutes=duree_minutes) <= end:
        creneaux.append(current)
        current += timedelta(minutes=30)

    # Récupérer RDV existants du praticien
    result = await db.execute(
        select(RendezVous)
        .where(RendezVous.clinic_id == clinic_id)
        .where(RendezVous.praticien_id == praticien_id)
        .where(RendezVous.date_heure_debut >= datetime.combine(date_jour, datetime.min.time()))
        .where(RendezVous.date_heure_debut < datetime.combine(date_jour + timedelta(days=1), datetime.min.time()))
        .where(RendezVous.statut.notin_([StatutRDV.ANNULE.value, StatutRDV.NO_SHOW.value]))
    )
    rdvs = result.scalars().all()

    # Filtrer les créneaux occupés
    creneaux_libres = []
    for creneau in creneaux:
        fin_creneau = creneau + timedelta(minutes=duree_minutes)
        occupe = False
        for rdv in rdvs:
            rdv_fin = rdv.date_heure_fin or rdv.date_heure_debut + timedelta(minutes=30)
            if not (fin_creneau <= rdv.date_heure_debut or creneau >= rdv_fin):
                occupe = True
                break
        if not occupe:
            creneaux_libres.append(creneau)

    return [
        {
            "heure": c.strftime("%H:%M"),
            "datetime": c.isoformat(),
        }
        for c in creneaux_libres
    ]


async def creer_rdv(
    patient_id: int,
    praticien_id: int,
    acte_id: int,
    date_heure: datetime,
    salle: Optional[str],
    db: AsyncSession,
    created_by: Optional[int] = None,
    clinic_id: Optional[int] = None,
) -> RendezVous:
    """Crée un rendez-vous.

    Détecte conflits praticien et salle.
    Calcule date_heure_fin selon durée acte.
    Vérifie consentement → badge alerte si manquant.
    """
    clinic_id = _resolve_clinic_id(clinic_id)

    # Récupérer durée acte
    result = await db.execute(
        select(ActeMedical).where(
            ActeMedical.id == acte_id,
            ActeMedical.clinic_id == clinic_id,
        )
    )
    acte = result.scalar_one_or_none()
    if not acte:
        raise ValueError("Acte non trouvé")

    duree = acte.duree_minutes
    date_fin = date_heure + timedelta(minutes=duree)

    # Vérifier conflit praticien
    conflit_praticien = await db.execute(
        select(RendezVous)
        .where(RendezVous.clinic_id == clinic_id)
        .where(RendezVous.praticien_id == praticien_id)
        .where(RendezVous.statut.notin_([StatutRDV.ANNULE.value, StatutRDV.NO_SHOW.value]))
        .where(
            and_(
                RendezVous.date_heure_debut < date_fin,
                RendezVous.date_heure_fin > date_heure,
            )
        )
    )
    if conflit_praticien.scalar_one_or_none():
        raise ValueError("Conflit : le praticien a déjà un RDV sur ce créneau")

    # Vérifier conflit salle
    if salle:
        conflit_salle = await db.execute(
            select(RendezVous)
            .where(RendezVous.clinic_id == clinic_id)
            .where(RendezVous.salle == salle)
            .where(RendezVous.statut.notin_([StatutRDV.ANNULE.value, StatutRDV.NO_SHOW.value]))
            .where(
                and_(
                    RendezVous.date_heure_debut < date_fin,
                    RendezVous.date_heure_fin > date_heure,
                )
            )
        )
        if conflit_salle.scalar_one_or_none():
            raise ValueError(f"Conflit : la salle {salle} est déjà occupée")

    # Vérifier consentement
    consentement_manquant = not await verify_consent(
        patient_id, acte_id, db, clinic_id=clinic_id
    )

    rdv = RendezVous(
        clinic_id=clinic_id,
        patient_id=patient_id,
        praticien_id=praticien_id,
        acte_id=acte_id,
        date_heure_debut=date_heure,
        date_heure_fin=date_fin,
        salle=salle,
        statut=StatutRDV.PLANIFIE.value,
        created_by=created_by,
    )
    db.add(rdv)
    await db.flush()

    # Notification WhatsApp confirmation
    patient_result = await db.execute(
        select(Patient).where(Patient.id == patient_id, Patient.clinic_id == clinic_id)
    )
    patient = patient_result.scalar_one()

    if patient.whatsapp_phone and not patient.opted_out:
        praticien_result = await db.execute(
            select(Utilisateur).where(
                Utilisateur.id == praticien_id, Utilisateur.clinic_id == clinic_id
            )
        )
        praticien = praticien_result.scalar_one()
        branding = await get_branding_context(db, clinic_id=clinic_id)

        message = (
            f"{branding['clinic_name']} — "
            + WA_TEMPLATES["rdv_confirmation"].format(
                date=date_heure.strftime("%d/%m/%Y"),
                heure=date_heure.strftime("%H:%M"),
                praticien=f"{praticien.prenom} {praticien.nom}",
            )
        )
        result = await send_whatsapp_message(patient.whatsapp_phone, message)
        if result.get("status") == "dev_mode":
            logger.warning(
                f"Rappel RDV confirmation non envoyé (WhatsApp non configuré) : patient_id={patient_id}"
            )

    return rdv, consentement_manquant


async def annuler_rdv(
    rdv_id: int, raison: str, db: AsyncSession, clinic_id: Optional[int] = None
) -> RendezVous:
    """Annule un RDV et envoie WhatsApp au patient."""
    clinic_id = _resolve_clinic_id(clinic_id)
    result = await db.execute(
        select(RendezVous).where(
            RendezVous.id == rdv_id, RendezVous.clinic_id == clinic_id
        )
    )
    rdv = result.scalar_one_or_none()
    if not rdv:
        raise ValueError("RDV non trouvé")

    rdv.statut = StatutRDV.ANNULE.value
    rdv.notes_post_acte = f"Annulé : {raison}"
    await db.flush()

    # Notification WhatsApp
    patient_result = await db.execute(select(Patient).where(Patient.id == rdv.patient_id))
    patient = patient_result.scalar_one()

    if patient.whatsapp_phone and not patient.opted_out:
        branding = await get_branding_context(db, clinic_id=clinic_id)
        message = (
            f"{branding['clinic_name']} — Votre rendez-vous du {rdv.date_heure_debut.strftime('%d/%m à %Hh%M')} a été annulé.\n"
            f"Raison : {raison}\nPour reprogrammer, répondez RDV."
        )
        result = await send_whatsapp_message(patient.whatsapp_phone, message)
        if result.get("status") == "dev_mode":
            logger.warning(
                f"Notification annulation non envoyée (WhatsApp non configuré) : patient_id={patient.id}"
            )

    return rdv


async def reminder_j1(db: AsyncSession):
    """Tâche Celery : rappel J-1 à 18h00.

    Tous les RDV de demain non annulés.
    WA : rappel + confirmation OUI/NON.
    Si NON → alerte secrétariat.
    """
    demain = date.today() + timedelta(days=1)
    debut = datetime.combine(demain, datetime.min.time())
    fin = datetime.combine(demain + timedelta(days=1), datetime.min.time())

    result = await db.execute(
        select(RendezVous, Patient, Utilisateur)
        .join(Patient, RendezVous.patient_id == Patient.id)
        .join(Utilisateur, RendezVous.praticien_id == Utilisateur.id)
        .where(RendezVous.date_heure_debut >= debut)
        .where(RendezVous.date_heure_debut < fin)
        .where(RendezVous.statut.in_([StatutRDV.PLANIFIE.value, StatutRDV.CONFIRME.value]))
        .where(not RendezVous.rappel_j1_envoye)
    )

    branding = await get_branding_context(db)

    for rdv, patient, praticien in result.all():
        if patient.whatsapp_phone and not patient.opted_out:
            message = (
                f"{branding['clinic_name']} — "
                + WA_TEMPLATES["rdv_rappel_j1"].format(
                    heure=rdv.date_heure_debut.strftime("%H:%M"),
                    praticien=f"{praticien.prenom} {praticien.nom}",
                )
            )
            result = await send_whatsapp_message(patient.whatsapp_phone, message)
            if result.get("status") == "dev_mode":
                logger.warning(
                    f"Rappel J-1 non envoyé (WhatsApp non configuré) : patient_id={patient.id}, rdv_id={rdv.id}"
                )
            else:
                rdv.rappel_j1_envoye = True

    await db.flush()


async def reminder_h2(db: AsyncSession):
    """Tâche Celery : rappel H-2.

    RDV dans exactement 2 heures.
    """
    now = datetime.utcnow()
    dans_2h = now + timedelta(hours=2)
    marge = timedelta(minutes=5)

    result = await db.execute(
        select(RendezVous, Patient)
        .join(Patient, RendezVous.patient_id == Patient.id)
        .where(RendezVous.date_heure_debut >= dans_2h - marge)
        .where(RendezVous.date_heure_debut <= dans_2h + marge)
        .where(RendezVous.statut.in_([StatutRDV.PLANIFIE.value, StatutRDV.CONFIRME.value]))
        .where(not RendezVous.rappel_h2_envoye)
    )

    branding = await get_branding_context(db)

    for rdv, patient in result.all():
        if patient.whatsapp_phone and not patient.opted_out:
            message = WA_TEMPLATES["rdv_rappel_h2"].format(
                clinique=branding["clinic_name"],
                adresse=branding["address"] or "Adresse communiquée par la clinique",
            )
            result = await send_whatsapp_message(patient.whatsapp_phone, message)
            if result.get("status") == "dev_mode":
                logger.warning(
                    f"Rappel H-2 non envoyé (WhatsApp non configuré) : patient_id={patient.id}, rdv_id={rdv.id}"
                )
            else:
                rdv.rappel_h2_envoye = True

    await db.flush()
