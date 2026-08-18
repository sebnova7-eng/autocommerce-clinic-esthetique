"""
AutoCommerce Clinic — Service messagerie interne d'équipe.
CRUD complet : envoyer, lister (boîte de réception), marquer lu, supprimer.
"""

from datetime import datetime
from typing import List, Optional

from sqlalchemy import select, and_, desc
from sqlalchemy.ext.asyncio import AsyncSession

from models.database import EquipeMessage, Utilisateur


async def envoyer_message(
    db: AsyncSession,
    expediteur_id: int,
    destinataire_id: int,
    sujet: str,
    contenu: str,
    clinic_id: int = 1,
) -> EquipeMessage:
    """Envoyer un message interne à un membre de l'équipe.

    Vérifie que le destinataire existe et est actif, puis crée le message.
    """
    # Vérifier que le destinataire existe
    dest_result = await db.execute(
        select(Utilisateur).where(
            and_(
                Utilisateur.id == destinataire_id,
                Utilisateur.clinic_id == clinic_id,
                Utilisateur.is_active,
            )
        )
    )
    destinataire = dest_result.scalar_one_or_none()
    if not destinataire:
        raise ValueError("Destinataire introuvable ou inactif dans la clinique")

    # Vérifier que l'expéditeur existe
    exp_result = await db.execute(
        select(Utilisateur).where(
            and_(
                Utilisateur.id == expediteur_id,
                Utilisateur.clinic_id == clinic_id,
                Utilisateur.is_active,
            )
        )
    )
    expediteur = exp_result.scalar_one_or_none()
    if not expediteur:
        raise ValueError("Expéditeur introuvable ou inactif")

    message = EquipeMessage(
        clinic_id=clinic_id,
        expediteur_id=expediteur_id,
        destinataire_id=destinataire_id,
        sujet=sujet,
        contenu=contenu,
        lu=False,
    )
    db.add(message)
    await db.flush()
    return message


async def lister_messages_reception(
    db: AsyncSession,
    utilisateur_id: int,
    clinic_id: int = 1,
    limit: int = 50,
    offset: int = 0,
) -> List[EquipeMessage]:
    """Lister les messages reçus par un utilisateur (boîte de réception)."""
    result = await db.execute(
        select(EquipeMessage)
        .where(
            and_(
                EquipeMessage.destinataire_id == utilisateur_id,
                EquipeMessage.clinic_id == clinic_id,
            )
        )
        .order_by(desc(EquipeMessage.cree_a))
        .limit(limit)
        .offset(offset)
    )
    return list(result.scalars().all())


async def lister_messages_envoyes(
    db: AsyncSession,
    utilisateur_id: int,
    clinic_id: int = 1,
    limit: int = 50,
    offset: int = 0,
) -> List[EquipeMessage]:
    """Lister les messages envoyés par un utilisateur."""
    result = await db.execute(
        select(EquipeMessage)
        .where(
            and_(
                EquipeMessage.expediteur_id == utilisateur_id,
                EquipeMessage.clinic_id == clinic_id,
            )
        )
        .order_by(desc(EquipeMessage.cree_a))
        .limit(limit)
        .offset(offset)
    )
    return list(result.scalars().all())


async def get_message(
    db: AsyncSession,
    message_id: int,
    utilisateur_id: int,
    clinic_id: int = 1,
) -> Optional[EquipeMessage]:
    """Récupérer un message spécifique si l'utilisateur est destinataire ou expéditeur."""
    result = await db.execute(
        select(EquipeMessage).where(
            and_(
                EquipeMessage.id == message_id,
                EquipeMessage.clinic_id == clinic_id,
                (EquipeMessage.destinataire_id == utilisateur_id)
                | (EquipeMessage.expediteur_id == utilisateur_id),
            )
        )
    )
    return result.scalar_one_or_none()


async def marquer_lu(
    db: AsyncSession,
    message_id: int,
    utilisateur_id: int,
    clinic_id: int = 1,
) -> Optional[EquipeMessage]:
    """Marquer un message comme lu. Seul le destinataire peut le faire."""
    message = await get_message(db, message_id, utilisateur_id, clinic_id)
    if not message:
        raise ValueError("Message introuvable ou accès refusé")

    if message.destinataire_id != utilisateur_id:
        raise ValueError("Seul le destinataire peut marquer un message comme lu")

    message.lu = True
    message.lu_a = datetime.utcnow()
    await db.flush()
    return message


async def supprimer_message(
    db: AsyncSession,
    message_id: int,
    utilisateur_id: int,
    clinic_id: int = 1,
) -> bool:
    """Supprimer un message. L'utilisateur doit être destinataire ou expéditeur."""
    message = await get_message(db, message_id, utilisateur_id, clinic_id)
    if not message:
        raise ValueError("Message introuvable ou accès refusé")

    await db.delete(message)
    await db.flush()
    return True


async def compter_non_lus(
    db: AsyncSession,
    utilisateur_id: int,
    clinic_id: int = 1,
) -> int:
    """Compter le nombre de messages non lus pour un utilisateur."""
    from sqlalchemy import func

    result = await db.execute(
        select(func.count(EquipeMessage.id))
        .where(
            and_(
                EquipeMessage.destinataire_id == utilisateur_id,
                EquipeMessage.clinic_id == clinic_id,
                not EquipeMessage.lu,
            )
        )
    )
    return result.scalar() or 0
