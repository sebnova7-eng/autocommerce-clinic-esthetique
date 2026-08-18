"""
AutoCommerce Clinic — Middleware Webhook Omnicanal (Bloc 1)

CORRECTION du webhook auth existant :
  - Supporte les signatures multi-canal (X-Hub-Signature-256, X-Tiktok-Signature)
  - Détecte automatiquement le canal à partir du payload
  - Dispatche vers le bon connecteur pour validation
  - Rétrocompatible avec l'ancien X-Signature (transition progressive)
"""

import json
import hashlib
import hmac
import logging
import time
from typing import Optional

from fastapi import Request
from sqlalchemy import select

from models.omnicanal import Conversation, MessageOmnicanal

logger = logging.getLogger(__name__)

# En-têtes de signature par canal
SIGNATURE_HEADERS = {
    "whatsapp": "X-Hub-Signature-256",
    "instagram": "X-Hub-Signature-256",
    "facebook": "X-Hub-Signature-256",
    "tiktok": "X-Tiktok-Signature",
    "email": None,  # Email n'a pas de webhook
    "sms": "X-Twilio-Signature",
}


async def get_channel_from_request(request: Request, path_canal: Optional[str] = None) -> Optional[str]:
    """Détecte le canal à partir du payload ou des headers.

    Utilise en priorité le path param (ex: /webhook/whatsapp) si le payload
    ne permet pas d'identifier le canal de manière fiable.
    """
    # Essayer de parser le body pour identifier le canal
    try:
        body = await request.body()
        data = json.loads(body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        data = {}

    # WhatsApp Meta
    if data.get("object") == "whatsapp_business_account":
        return "whatsapp"
    # Instagram Meta
    if data.get("object") == "instagram":
        return "instagram"
    # Facebook Meta
    if data.get("object") == "page":
        # Peut être Instagram ou Facebook — vérifier les champs
        entries = data.get("entry", [{}])
        if entries and "messaging" in entries[0]:
            # Facebook Messenger utilise 'messaging'
            return "facebook"
        return "instagram"  # Fallback
    # TikTok
    if "X-Tiktok-Signature" in request.headers:
        return "tiktok"
    # Twilio SMS
    if "X-Twilio-Signature" in request.headers:
        return "sms"
    # Header explicite
    canal_header = request.headers.get("X-Channel")
    if canal_header:
        return canal_header

    # Fallback : utiliser le path param si fourni
    if path_canal and path_canal in ("whatsapp", "instagram", "facebook", "tiktok", "sms", "email"):
        return path_canal

    return None


async def verify_webhook_signature(request: Request, channel: str, secret: Optional[str]) -> bool:
    """Vérifie la signature du webhook pour un canal donné.

    `secret` doit déjà être le bon secret pour ce canal (Meta pour
    whatsapp/instagram/facebook, TikTok pour tiktok) — voir
    process_incoming_webhook, qui sélectionne le bon avant d'appeler
    cette fonction. Ne jamais réutiliser le secret Meta pour TikTok."""
    if not secret:
        return False

    raw_body = await request.body()
    header_name = SIGNATURE_HEADERS.get(channel, "X-Signature")

    signature = request.headers.get(header_name) or request.headers.get("X-Signature")
    if not signature:
        return False

    hex_hash = signature
    if signature.startswith("sha256="):
        hex_hash = signature[len("sha256="):]

    expected = hmac.new(
        secret.encode(),
        raw_body,
        hashlib.sha256,
    ).hexdigest()

    return hmac.compare_digest(hex_hash, expected)


async def process_incoming_webhook(request: Request, db, clinic_id: int = 1, path_canal: Optional[str] = None) -> dict:
    """Traite un webhook entrant multi-canal."""
    from config import get_settings
    from services.omnicanal_service import receive_message
    from services.omnicanal.factory import OmnicanalFactory
    from middleware.assistant_whitelist import resolve_user_from_whitelist, WhitelistRejection
    from services.clinic_agent import handle_agent_message
    from services.voice_transcription import transcribe_whatsapp_voice

    settings = get_settings()

    # Détecter le canal d'abord : le secret dépend du canal (Meta et
    # TikTok ont chacun leur propre secret, jamais partagé entre les deux).
    channel = await get_channel_from_request(request, path_canal=path_canal)
    if not channel:
        logger.warning("Could not identify channel from webhook payload")
        return {"error": "Canal non identifiable", "success": False}

    channel_secrets = {
        "whatsapp": settings.social_webhook_secret,
        "instagram": settings.social_webhook_secret,
        "facebook": settings.social_webhook_secret,
        "tiktok": settings.tiktok_webhook_secret,
    }
    secret = channel_secrets.get(channel)

    if not secret:
        logger.error(f"Webhook secret missing for channel={channel}")
        return {"error": f"Webhook non configuré pour {channel}", "success": False}

    # Vérification des feature flags
    disabled = False
    if channel == "tiktok" and not settings.tiktok_enabled:
        disabled = True
    elif channel == "instagram" and not settings.instagram_enabled:
        disabled = True
    elif channel == "facebook" and not settings.facebook_enabled:
        disabled = True
    
    if disabled:
        logger.warning(f"Webhook received for disabled channel: {channel}")
        return {"error": f"Canal {channel} désactivé", "success": False}

    # Récupérer le connecteur pour la vérification de signature
    factory = OmnicanalFactory()
    connector = factory.get_connector(channel)
    raw_body = await request.body()
    
    header_name = SIGNATURE_HEADERS.get(channel) or "X-Signature"
    sig = request.headers.get(header_name) or request.headers.get("X-Signature")

    if connector:
        if sig:
            if not connector.verify_signature(raw_body, sig):
                return {"error": "Signature invalide", "success": False}
        else:
            if not await verify_webhook_signature(request, channel, secret):
                return {"error": "Signature manquante ou invalide", "success": False}
    else:
        if not await verify_webhook_signature(request, channel, secret):
            return {"error": "Signature manquante ou invalide", "success": False}

    # Parser le payload
    if connector:
        messages_data = connector.parse_webhook_payload(raw_body)
    else:
        messages_data = []

    # Enregistrer chaque message
    results = []
    for msg_data in messages_data:
        external_message_id = msg_data.get("external_message_id")
        if external_message_id:
            existing = await db.scalar(
                select(MessageOmnicanal.id)
                .join(Conversation, Conversation.id == MessageOmnicanal.conversation_id)
                .where(
                    MessageOmnicanal.clinic_id == clinic_id,
                    MessageOmnicanal.external_message_id == external_message_id,
                    Conversation.canal == channel,
                    MessageOmnicanal.direction == "entrant",
                )
            )
            if existing is not None:
                logger.info("webhook_duplicate_skipped channel=%s external_message_id=%s", channel, external_message_id)
                results.append({"duplicate": True, "external_message_id": external_message_id})
                continue

        raw_timestamp = msg_data.get("timestamp")
        if raw_timestamp is not None:
            try:
                timestamp = float(raw_timestamp)
                if timestamp > 10_000_000_000:
                    timestamp /= 1000
                if abs(time.time() - timestamp) > 300:
                    logger.warning("webhook_old_message_rejected channel=%s external_message_id=%s", channel, external_message_id)
                    results.append({"rejected": True, "reason": "timestamp_expired", "external_message_id": external_message_id})
                    continue
            except (TypeError, ValueError):
                results.append({"rejected": True, "reason": "invalid_timestamp", "external_message_id": external_message_id})
                continue

        # Les vocaux doivent être transcrits avant toute persistance afin que
        # l'inbox, les workflows et l'agent IA reçoivent le contenu réel.
        # media_url contient ici l'ID média Meta (pas une URL publique).
        processed_content = msg_data.get("content", "")
        transcription_failed = False
        if channel == "whatsapp" and msg_data.get("type_message") == "audio" and msg_data.get("media_url"):
            transcribed = await transcribe_whatsapp_voice(msg_data["media_url"])
            if transcribed:
                processed_content = transcribed
            else:
                transcription_failed = True

        # Un numéro WhatsApp whitelisté (staff) est traité par l'agent IA,
        # pas comme un message patient classique dans l'inbox générique.
        # C'était câblé nulle part jusqu'ici : le module assistant/agent
        # (whitelist, RBAC, confirmation) était fonctionnel mais jamais
        # atteint par un vrai message WhatsApp entrant.
        if channel == "whatsapp":
            try:
                _, staff_user = await resolve_user_from_whitelist(msg_data["contact_id"], db)
                current_user = {
                    "id": staff_user.id, "role": staff_user.role,
                    "nom": staff_user.nom, "prenom": staff_user.prenom,
                    "email": staff_user.email,
                }

                question = None if transcription_failed else processed_content

                if question:
                    agent_result = await handle_agent_message(
                        msg_data["contact_id"], question, current_user, db
                    )
                else:
                    agent_result = {
                        "reponse": "Je n'ai pas pu comprendre ce message vocal, pouvez-vous réessayer ou l'écrire ?",
                        "statut": "transcription_echouee",
                    }
                results.append({"canal": "whatsapp", "agent": True, **agent_result})
                continue
            except WhitelistRejection:
                pass  # pas un numéro staff → traitement patient normal ci-dessous

        result = await receive_message(
            canal=channel,
            contact_external_id=msg_data["contact_id"],
            content=processed_content,
            type_message=msg_data.get("type_message", "texte"),
            media_url=msg_data.get("media_url"),
            external_message_id=msg_data.get("external_message_id"),
            clinic_id=clinic_id,
            db=db,
        )
        results.append(result)

    logger.info(f"Webhook {channel} processed: {len(results)} messages persisted")
    return {
        "canal": channel,
        "messages_count": len(results),
        "success": True,
        "results": results,
    }
