"""AutoCommerce Clinic — Automatisations fidélité
Tâches planifiées (Celery) : anniversaire, relance inactivité, expiration des points.

Ce module manquait dans une livraison précédente alors que
services/celery_app.py l'importait déjà — les 3 tâches plantaient
silencieusement à chaque exécution planifiée sans que rien ne le
signale (import différé dans le corps de chaque tâche Celery).
"""
import logging
from datetime import date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.database import Patient, FideliteTransaction
from services.fidelite import add_points
from services.whatsapp_service import send_whatsapp_message
from config import get_settings, WA_TEMPLATES

logger = logging.getLogger(__name__)

settings = get_settings()

# Pas encore un réglage exposé côté settings/branding — durée avant de
# considérer une patiente comme inactive et de lui envoyer une relance.
INACTIVITE_MOIS = 3
ANNIVERSAIRE_POINTS = 100


async def check_anniversaire(db: AsyncSession) -> int:
    """Envoie un message + 100 points aux patientes dont c'est l'anniversaire
    aujourd'hui. Idempotent : ne réattribue pas si déjà fait aujourd'hui."""
    today = date.today()
    result = await db.execute(
        select(Patient).where(
            Patient.anonymized_at.is_(None),
            Patient.opted_out.is_(False),
            Patient.date_naissance.is_not(None),
        )
    )
    patients = [
        p for p in result.scalars().all()
        if p.date_naissance.month == today.month and p.date_naissance.day == today.day
    ]

    count = 0
    for patient in patients:
        already = await db.execute(
            select(FideliteTransaction).where(
                FideliteTransaction.patient_id == patient.id,
                FideliteTransaction.motif == "anniversaire",
                FideliteTransaction.created_at >= datetime(today.year, today.month, today.day),
            )
        )
        if already.scalar_one_or_none():
            continue

        await add_points(patient.id, ANNIVERSAIRE_POINTS, "anniversaire", db)
        if patient.whatsapp_phone:
            message = WA_TEMPLATES["anniversaire"].format(prenom=patient.prenom)
            result = await send_whatsapp_message(patient.whatsapp_phone, message)
            if result.get("status") == "dev_mode":
                logger.warning(
                    f"Message anniversaire non envoyé (WhatsApp non configuré) : patient_id={patient.id}"
                )
        count += 1

    await db.flush()
    return count


async def check_inactivite(db: AsyncSession) -> int:
    """Relance les patientes sans visite depuis INACTIVITE_MOIS mois."""
    seuil = date.today() - timedelta(days=INACTIVITE_MOIS * 30)
    result = await db.execute(
        select(Patient).where(
            Patient.anonymized_at.is_(None),
            Patient.opted_out.is_(False),
            Patient.derniere_visite.is_not(None),
            Patient.derniere_visite < seuil,
        )
    )
    patients = result.scalars().all()

    count = 0
    for patient in patients:
        if not patient.whatsapp_phone:
            continue
        message = WA_TEMPLATES["relance_inactive"].format(prenom=patient.prenom)
        result = await send_whatsapp_message(patient.whatsapp_phone, message)
        if result.get("status") == "dev_mode":
            logger.warning(
                f"Relance inactivité non envoyée (WhatsApp non configuré) : patient_id={patient.id}"
            )
        count += 1

    return count


async def expire_points(db: AsyncSession) -> int:
    """Expire les points des patientes sans transaction fidélité depuis
    settings.points_expiry_months mois."""
    seuil = datetime.utcnow() - timedelta(days=settings.points_expiry_months * 30)

    result = await db.execute(
        select(Patient).where(
            Patient.anonymized_at.is_(None),
            Patient.points_fidelite > 0,
        )
    )
    patients = result.scalars().all()

    count = 0
    for patient in patients:
        last_tx = await db.execute(
            select(FideliteTransaction)
            .where(FideliteTransaction.patient_id == patient.id)
            .order_by(FideliteTransaction.created_at.desc())
            .limit(1)
        )
        last = last_tx.scalar_one_or_none()
        last_activity = last.created_at if last else None

        if last_activity and last_activity > seuil:
            continue  # activité récente, rien à expirer

        points_a_expirer = patient.points_fidelite
        if points_a_expirer <= 0:
            continue

        patient.points_fidelite = 0
        db.add(FideliteTransaction(
            clinic_id=patient.clinic_id,
            patient_id=patient.id,
            type="expiration",
            points=-points_a_expirer,
            solde_apres=0,
            motif="Expiration automatique (inactivité > points_expiry_months)",
        ))
        count += 1

    await db.flush()
    return count
