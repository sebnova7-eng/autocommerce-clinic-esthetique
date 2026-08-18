"""
AutoCommerce Clinic — Service de rappels post-injection
"""

import logging
from datetime import date

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from models.database import UtilisationLot, LotInjectable
from services.omnicanal_service import get_or_create_conversation, send_reply

logger = logging.getLogger(__name__)

async def process_injection_reminders(db: AsyncSession):
    """
    Scanne les utilisations de lots pour envoyer des rappels automatiques
    quand la date de prochaine injection est arrivée.
    """
    today = date.today()
    
    # 1. Rechercher les utilisations arrivant à échéance aujourd'hui ou avant
    # et n'ayant pas encore reçu de rappel.
    stmt = (
        select(UtilisationLot)
        .options(
            joinedload(UtilisationLot.patient),
            joinedload(UtilisationLot.lot).joinedload(LotInjectable.produit)
        )
        .where(
            and_(
                UtilisationLot.prochaine_injection_date <= today,
                UtilisationLot.prochaine_injection_envoyee.is_(False),
                UtilisationLot.prochaine_injection_date.isnot(None)
            )
        )
    )
    
    result = await db.execute(stmt)
    utilisations = result.scalars().all()
    
    count = 0
    for util in utilisations:
        try:
            success = await send_injection_reminder(util, db)
            if success:
                util.prochaine_injection_envoyee = True
                count += 1
        except Exception as e:
            logger.error(f"Erreur lors de l'envoi du rappel pour l'utilisation {util.id}: {e}")
            
    await db.commit()
    return count

async def send_injection_reminder(utilisation: UtilisationLot, db: AsyncSession) -> bool:
    """Envoie le rappel via WhatsApp."""
    patient = utilisation.patient
    produit = utilisation.lot.produit
    
    if not patient.whatsapp_phone:
        logger.warning(f"Patient {patient.id} n'a pas de numéro WhatsApp configuré.")
        return False
        
    # 1. Trouver ou créer la conversation
    conversation = await get_or_create_conversation(
        canal="whatsapp",
        contact_external_id=patient.whatsapp_phone,
        patient_id=patient.id,
        clinic_id=utilisation.clinic_id,
        db=db
    )
    
    # 2. Envoyer le message via template
    template_params = {
        "prenom": patient.prenom,
        "produit": produit.nom,
        "date": utilisation.prochaine_injection_date.strftime("%d/%m/%Y")
    }
    
    # Le contenu textuel est généré à partir du template dans config.py
    # mais send_reply s'occupe de la logique de dispatching.
    # Note: Dans ce système, le contenu est souvent passé explicitement ou résolu par le connecteur.
    
    from config import WA_TEMPLATES
    content = WA_TEMPLATES["injection_rappel"].format(**template_params)
    
    result = await send_reply(
        conversation_id=conversation.id,
        content=content,
        template_name="injection_rappel",
        template_params=template_params,
        clinic_id=utilisation.clinic_id,
        db=db
    )
    
    return result.get("message") is not None and result["message"].statut != "echec"
