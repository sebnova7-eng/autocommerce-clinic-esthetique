"""
AutoCommerce Clinic — Service Omnicanal (Bloc 1)

Service métier principal qui orchestre les connecteurs de canaux.
Gère les conversations, messages, événements et l'intégration avec
le service social_crm existant (rétrocompatibilité garantie).

Rétrocompatibilité :
  - Les anciennes tables social_messages et social_posts continuent d'exister
  - Le service social_crm.py continue de fonctionner sans modification
  - Ce service utilise les NOUVELLES tables (conversations, messages_omnicanal)
  - Un pont est maintenu pour que les webhooks alimentent les DEUX systèmes
    durant la période de transition
"""

import json
from datetime import datetime
from typing import List, Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from models.omnicanal import (
    CanalEnum,
    ChannelConfig,
    ChannelEvent,
    Conversation,
    MessageOmnicanal,
    StatutMessageEnum,
)
from models.database import Patient
from services.omnicanal.factory import get_connector, get_canal_labels


# ═══════════════════════════════════════════════════════════
# CONVERSATIONS
# ═══════════════════════════════════════════════════════════

async def get_or_create_conversation(
    canal: str,
    contact_external_id: str,
    contact_nom: Optional[str] = None,
    patient_id: Optional[int] = None,
    clinic_id: int = 1,
    db: Optional[AsyncSession] = None,
) -> Conversation:
    """Récupère ou crée une conversation pour un contact sur un canal donné.
    
    Chaque contact unique sur un canal donné a une conversation unique.
    Si le patient est identifié, la conversation est liée au dossier patient.
    """
    # Chercher une conversation existante
    result = await db.execute(
        select(Conversation).where(
            Conversation.clinic_id == clinic_id,
            Conversation.canal == canal,
            Conversation.contact_external_id == contact_external_id,
        )
    )
    conversation = result.scalar_one_or_none()

    if conversation:
        # Mettre à jour le nom du contact si changé
        if contact_nom:
            conversation.contact_nom = contact_nom
        if patient_id and not conversation.patient_id:
            conversation.patient_id = patient_id
        await db.flush()
        return conversation

    # Créer une nouvelle conversation
    conversation = Conversation(
        clinic_id=clinic_id,
        canal=canal,
        contact_external_id=contact_external_id,
        contact_nom=contact_nom,
        patient_id=patient_id,
        statut="ouverte",
    )
    db.add(conversation)
    await db.flush()
    return conversation


async def list_conversations(
    db: AsyncSession,
    canal: Optional[str] = None,
    statut: Optional[str] = None,
    patient_id: Optional[int] = None,
    clinic_id: int = 1,
    limit: int = 50,
    offset: int = 0,
) -> List[Conversation]:
    """Liste les conversations avec filtres."""
    query = select(Conversation).where(Conversation.clinic_id == clinic_id)
    if canal:
        query = query.where(Conversation.canal == canal)
    if statut:
        query = query.where(Conversation.statut == statut)
    if patient_id:
        query = query.where(Conversation.patient_id == patient_id)
    query = query.order_by(Conversation.dernier_message_at.desc().nullslast())
    query = query.offset(offset).limit(limit)

    result = await db.execute(query)
    return list(result.scalars().all())


async def close_conversation(conversation_id: int, db: AsyncSession, clinic_id: int = 1) -> Conversation:
    """Ferme une conversation appartenant à la clinique du contexte."""
    result = await db.execute(
        select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.clinic_id == clinic_id,
        )
    )
    conversation = result.scalar_one_or_none()
    if not conversation:
        raise ValueError("Conversation non trouvée")
    conversation.statut = "fermee"
    await db.flush()
    return conversation


async def assign_conversation(conversation_id: int, assignee_id: int, db: AsyncSession) -> Conversation:
    """Assigne une conversation à un utilisateur."""
    result = await db.execute(
        select(Conversation).where(Conversation.id == conversation_id)
    )
    conversation = result.scalar_one_or_none()
    if not conversation:
        raise ValueError("Conversation non trouvée")
    conversation.assignee_id = assignee_id
    if conversation.statut == "fermee":
        conversation.statut = "ouverte"
    await db.flush()
    return conversation


async def add_tags_to_conversation(conversation_id: int, tags: List[str], db: AsyncSession) -> Conversation:
    """Ajoute des tags à une conversation."""
    result = await db.execute(
        select(Conversation).where(Conversation.id == conversation_id)
    )
    conversation = result.scalar_one_or_none()
    if not conversation:
        raise ValueError("Conversation non trouvée")
    existing_tags = json.loads(conversation.tags) if conversation.tags else []
    for tag in tags:
        if tag not in existing_tags:
            existing_tags.append(tag)
    conversation.tags = json.dumps(existing_tags)
    await db.flush()
    return conversation


# ═══════════════════════════════════════════════════════════
# MESSAGES
# ═══════════════════════════════════════════════════════════

async def receive_message(
    canal: str,
    contact_external_id: str,
    content: str,
    type_message: str = "texte",
    media_url: Optional[str] = None,
    external_message_id: Optional[str] = None,
    clinic_id: int = 1,
    db: Optional[AsyncSession] = None,
) -> dict:
    """Enregistre un message entrant dans une conversation.
    
    Réutilise la logique de matching patient du service social_crm existant,
    mais écrit dans les NOUVELLES tables omnicanal.
    
    Returns:
        {
            "conversation": Conversation,
            "message": MessageOmnicanal,
            "patient_matched": Patient | None,
        }
    """
    # Valider le canal
    valid_canaux = [c.value for c in CanalEnum]
    if canal not in valid_canaux:
        raise ValueError(f"Canal non supporté : {canal}. Canaux valides : {valid_canaux}")

    # Trouver ou créer la conversation
    conversation = await get_or_create_conversation(
        canal=canal,
        contact_external_id=contact_external_id,
        clinic_id=clinic_id,
        db=db,
    )

    # Matching patient (réutilise la logique existante)
    patient_id = None
    if canal == "whatsapp":
        result = await db.execute(
            select(Patient).where(Patient.whatsapp_phone == contact_external_id)
        )
        patient = result.scalar_one_or_none()
        if patient:
            patient_id = patient.id
            conversation.patient_id = patient.id
            conversation.contact_nom = f"{patient.prenom} {patient.nom}"

    # Créer le message
    pieces_jointes = None
    if media_url:
        pieces_jointes = json.dumps([{"type": type_message, "url": media_url}])

    message = MessageOmnicanal(
        clinic_id=clinic_id,
        conversation_id=conversation.id,
        direction="entrant",
        type_message=type_message,
        contenu=content,
        pieces_jointes=pieces_jointes,
        statut=StatutMessageEnum.ENVOYE.value,
        external_message_id=external_message_id,
        patient_id=patient_id,
    )
    db.add(message)

    # Mettre à jour la conversation
    conversation.dernier_message_at = datetime.utcnow()
    conversation.nb_messages += 1

    # Flush d'abord pour obtenir l'ID du message
    await db.flush()

    # Enregistrer l'événement (après flush pour avoir message.id)
    event = ChannelEvent(
        clinic_id=clinic_id,
        message_id=message.id,
        conversation_id=conversation.id,
        type_evenement="received",
        timestamp=datetime.utcnow(),
    )
    db.add(event)
    await db.flush()

    return {
        "conversation": conversation,
        "message": message,
        "patient_matched": patient_id is not None,
    }


async def send_reply(
    conversation_id: int,
    content: str,
    db: AsyncSession,
    type_message: str = "texte",
    media_url: Optional[str] = None,
    template_name: Optional[str] = None,
    template_params: Optional[dict] = None,
    envoye_par_id: Optional[int] = None,
    clinic_id: int = 1,
) -> dict:
    """Envoie une réponse via le canal approprié.
    
    Dispatche le message au connecteur du canal de la conversation.
    En mode dev (pas de credentials), retourne succès honnête.
    
    Returns:
        {
            "message": MessageOmnicanal,
            "result": dict (résultat du connecteur),
        }
    """
    # Récupérer la conversation
    result = await db.execute(
        select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.clinic_id == clinic_id,
        )
    )
    conversation = result.scalar_one_or_none()
    if not conversation:
        raise ValueError("Conversation non trouvée")

    # Récupérer le connecteur
    connector = get_connector(conversation.canal)
    if not connector:
        # Canal non supporté → marquer en échec
        message = MessageOmnicanal(
            clinic_id=clinic_id,
            conversation_id=conversation_id,
            direction="sortant",
            type_message=type_message,
            contenu=content,
            statut=StatutMessageEnum.ECHEC.value,
            erreur=f"Canal '{conversation.canal}' non configuré",
            envoye_par_id=envoye_par_id,
        )
        db.add(message)
        await db.flush()
        return {"message": message, "result": {"status": "not_configured"}}

    # Construire les pièces jointes
    pieces_jointes = None
    if media_url:
        pieces_jointes = json.dumps([{"type": type_message, "url": media_url}])

    # Créer le message (brouillon pendant l'envoi)
    message = MessageOmnicanal(
        clinic_id=clinic_id,
        conversation_id=conversation_id,
        direction="sortant",
        type_message=type_message,
        contenu=content,
        pieces_jointes=pieces_jointes,
        statut=StatutMessageEnum.ENVOI_EN_COURS.value,
        template_name=template_name,
        template_params=json.dumps(template_params) if template_params else None,
        patient_id=conversation.patient_id,
        envoye_par_id=envoye_par_id,
    )
    db.add(message)
    await db.flush()

    # Envoyer via le connecteur
    if media_url and type_message in ("image", "video", "audio", "pdf", "document"):
        send_result = await connector.send_media(
            contact_id=conversation.contact_external_id,
            media_type=type_message,
            media_url=media_url,
        )
    else:
        send_result = await connector.send_message(
            contact_id=conversation.contact_external_id,
            content=content,
            template_name=template_name,
            template_params=template_params,
        )

    # Mettre à jour le message avec le résultat
    if send_result.get("success"):
        message.statut = StatutMessageEnum.ENVOYE.value
        message.external_message_id = send_result.get("external_message_id")
        conversation.dernier_message_at = datetime.utcnow()
        conversation.nb_messages += 1
    else:
        message.statut = StatutMessageEnum.ECHEC.value
        message.erreur = send_result.get("details", "Erreur d'envoi")
        message.nb_retries += 1

    # Enregistrer l'événement
    event_type = "sent" if send_result.get("success") else "failed"
    event = ChannelEvent(
        clinic_id=clinic_id,
        message_id=message.id,
        conversation_id=conversation_id,
        type_evenement=event_type,
        details=json.dumps(send_result.get("details", {})) if isinstance(send_result.get("details"), dict) else str(send_result.get("details", "")),
        timestamp=datetime.utcnow(),
    )
    db.add(event)

    await db.flush()

    return {"message": message, "result": send_result}


async def list_messages(
    db: AsyncSession,
    conversation_id: Optional[int] = None,
    canal: Optional[str] = None,
    statut: Optional[str] = None,
    patient_id: Optional[int] = None,
    clinic_id: int = 1,
    limit: int = 100,
    offset: int = 0,
) -> List[MessageOmnicanal]:
    """Liste les messages avec filtres."""
    query = select(MessageOmnicanal).where(MessageOmnicanal.clinic_id == clinic_id)
    if conversation_id:
        query = query.where(MessageOmnicanal.conversation_id == conversation_id)
    if canal:
        # Filtrer par canal via la conversation
        conv_ids = await db.execute(
            select(Conversation.id).where(Conversation.clinic_id == clinic_id, Conversation.canal == canal)
        )
        conv_ids_list = [r[0] for r in conv_ids.all()]
        if conv_ids_list:
            query = query.where(MessageOmnicanal.conversation_id.in_(conv_ids_list))
        else:
            return []
    if statut:
        query = query.where(MessageOmnicanal.statut == statut)
    if patient_id:
        query = query.where(MessageOmnicanal.patient_id == patient_id)
    query = query.order_by(MessageOmnicanal.created_at.desc())
    query = query.offset(offset).limit(limit)

    result = await db.execute(query)
    return list(result.scalars().all())


async def get_conversation_messages(
    conversation_id: int,
    db: AsyncSession,
    limit: int = 200,
    offset: int = 0,
    clinic_id: int = 1,
) -> List[MessageOmnicanal]:
    """Récupère tous les messages d'une conversation (thread)."""
    result = await db.execute(
        select(MessageOmnicanal)
        .where(
            MessageOmnicanal.conversation_id == conversation_id,
            MessageOmnicanal.clinic_id == clinic_id,
        )
        .order_by(MessageOmnicanal.created_at.asc())
        .offset(offset)
        .limit(limit)
    )
    return list(result.scalars().all())


# ═══════════════════════════════════════════════════════════
# ACCUSÉS DE RÉCEPTION
# ═══════════════════════════════════════════════════════════

async def update_delivery_status(
    external_message_id: str,
    status: str,
    db: AsyncSession,
    raw_payload: Optional[dict] = None,
) -> Optional[MessageOmnicanal]:
    """Met à jour le statut de livraison d'un message (webhook callback).
    
    Statuts : sent | delivered | read | failed
    """
    result = await db.execute(
        select(MessageOmnicanal).where(
            MessageOmnicanal.external_message_id == external_message_id
        )
    )
    message = result.scalar_one_or_none()
    if not message:
        return None

    if status == "delivered":
        message.statut = StatutMessageEnum.DELIVRE.value
        message.delivre_a = datetime.utcnow()
    elif status == "read":
        message.statut = StatutMessageEnum.LU.value
        message.lu_a = datetime.utcnow()
    elif status == "failed":
        message.statut = StatutMessageEnum.ECHEC.value

    # Enregistrer l'événement
    event = ChannelEvent(
        clinic_id=message.clinic_id,
        message_id=message.id,
        conversation_id=message.conversation_id,
        type_evenement=status,
        raw_payload=json.dumps(raw_payload) if raw_payload else None,
        timestamp=datetime.utcnow(),
    )
    db.add(event)
    await db.flush()

    return message


# ═══════════════════════════════════════════════════════════
# RETRY
# ═══════════════════════════════════════════════════════════

async def retry_failed_message(message_id: int, db: AsyncSession) -> dict:
    """Tente de renvoyer un message en échec."""
    result = await db.execute(
        select(MessageOmnicanal).where(MessageOmnicanal.id == message_id)
    )
    message = result.scalar_one_or_none()
    if not message:
        raise ValueError("Message non trouvé")

    if message.statut != StatutMessageEnum.ECHEC.value:
        raise ValueError("Ce message n'est pas en échec")

    if message.nb_retries >= message.max_retries:
        raise ValueError(f"Nombre maximum de retries atteint ({message.max_retries})")

    # Récupérer la conversation
    conv_result = await db.execute(
        select(Conversation).where(Conversation.id == message.conversation_id)
    )
    conversation = conv_result.scalar_one_or_none()
    if not conversation:
        raise ValueError("Conversation associée non trouvée")

    connector = get_connector(conversation.canal)
    if not connector:
        raise ValueError(f"Connecteur pour le canal '{conversation.canal}' non disponible")

    # Retenter l'envoi
    send_result = await connector.send_message(
        contact_id=conversation.contact_external_id,
        content=message.contenu or "",
        template_name=message.template_name,
    )

    message.nb_retries += 1
    message.dernier_retry_at = datetime.utcnow()

    if send_result.get("success"):
        message.statut = StatutMessageEnum.ENVOYE.value
        message.external_message_id = send_result.get("external_message_id")
        message.erreur = None
    else:
        message.erreur = f"Retry échoué ({message.nb_retries}/{message.max_retries}): {send_result.get('details')}"

    # Event
    event = ChannelEvent(
        clinic_id=message.clinic_id,
        message_id=message.id,
        conversation_id=message.conversation_id,
        type_evenement="retry",
        details=json.dumps(send_result),
        timestamp=datetime.utcnow(),
    )
    db.add(event)
    await db.flush()

    return {"message": message, "result": send_result}


# ═══════════════════════════════════════════════════════════
# ANALYTICS
# ═══════════════════════════════════════════════════════════

async def get_omnicanal_analytics(db: AsyncSession, clinic_id: int = 1) -> dict:
    """Agrège les statistiques omnicanal."""
    stats: dict = {
        "conversations": {},
        "messages": {},
        "by_platform": {},
    }

    # Compter par canal
    for canal in CanalEnum:
        # Conversations actives
        conv_result = await db.execute(
            select(func.count(Conversation.id)).where(
                Conversation.clinic_id == clinic_id,
                Conversation.canal == canal.value,
                Conversation.statut == "ouverte",
            )
        )
        nb_conv = conv_result.scalar() or 0

        # Messages aujourd'hui
        today = datetime.utcnow().date()
        msg_result = await db.execute(
            select(func.count(MessageOmnicanal.id)).where(
                MessageOmnicanal.clinic_id == clinic_id,
                MessageOmnicanal.conversation_id.in_(
                    select(Conversation.id).where(
                        Conversation.clinic_id == clinic_id,
                        Conversation.canal == canal.value,
                    )
                ),
                func.date(MessageOmnicanal.created_at) == today,
            )
        )
        nb_msg = msg_result.scalar() or 0

        stats["by_platform"][canal.value] = {
            "conversations_actives": nb_conv,
            "messages_aujourdhui": nb_msg,
        }

    # Totaux
    total_conv = await db.execute(
        select(func.count(Conversation.id)).where(
            Conversation.clinic_id == clinic_id,
            Conversation.statut == "ouverte",
        )
    )
    stats["total_conversations"] = int(total_conv.scalar() or 0)

    return stats


# ═══════════════════════════════════════════════════════════
# MESSAGE GÉNÉRIQUE (pour workflow engine)
# ═══════════════════════════════════════════════════════════

async def send_message(
    channel: str,
    to: str,
    content: str,
    subject: Optional[str] = None,
) -> dict:
    """Fonction générique d'envoi de message omnicanal.
    Wrapper pour l'appel depuis le workflow engine.
    Utilise le connecteur réel du canal pour un envoi authentique.
    Retourne un dict compatible avec les attentes du workflow.

    CORRECTION AUDIT : remplace le mode simulé permanent par un appel
    réel au connecteur du canal. Si le canal n'est pas configuré,
    retourne un échec explicite au lieu d'un faux succès.
    """
    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"send_message called: channel={channel}, to={to}, subject={subject}")

    connector = get_connector(channel)
    if not connector:
        logger.warning(f"send_message: canal '{channel}' non configuré")
        return {
            "success": False,
            "id": None,
            "channel": channel,
            "to": to,
            "details": f"Canal '{channel}' non configuré — aucun connecteur disponible",
        }

    # Envoyer via le connecteur réel du canal
    if channel == "email":
        send_result = await connector.send_message(
            contact_id=to,
            content=content,
            subject=subject,
        )
    else:
        send_result = await connector.send_message(
            contact_id=to,
            content=content,
        )

    return {
        "success": send_result.get("success", False),
        "id": send_result.get("external_message_id"),
        "channel": channel,
        "to": to,
        "details": send_result.get("details", ""),
        "status": send_result.get("status", "unknown"),
    }


async def get_channel_stats(db: AsyncSession, clinic_id: int = 1) -> dict:
    """Retourne le statut de chaque canal configuré."""
    labels = get_canal_labels()
    result = await db.execute(
        select(ChannelConfig).where(ChannelConfig.clinic_id == clinic_id)
    )
    configs = result.scalars().all()

    stats = {}
    for canal in CanalEnum:
        canal_data = labels.get(canal.value, {})
        # Trouver la config
        config = next((c for c in configs if c.canal == canal.value), None)
        status = config.statut if config else "non_configure"

        stats[canal.value] = {
            "label": canal_data.get("label", canal.value),
            "color": canal_data.get("color"),
            "icon": canal_data.get("icon"),
            "status": status,
            "limitations": canal_data.get("limitations", ""),
            "config_required": canal_data.get("config_required", []),
            "messages_envoyes_aujourdhui": config.messages_envoyes_aujourdhui if config else 0,
            "messages_par_jour": config.messages_par_jour if config else 0,
        }

    return stats
