"""
AutoCommerce Clinic — Service WhatsApp Business API
Envoi de messages via Meta Graph API
"""

import logging
import httpx
from config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)


async def send_whatsapp_message(to_phone: str, message: str) -> dict:
    """Envoie un message WhatsApp texte simple.

    Args:
        to_phone: Numéro au format international (+216XXXXXXXX)
        message: Texte du message (max 4096 caractères)

    Returns:
        Réponse de l'API Meta
    """
    if not settings.wa_business_token or not settings.wa_phone_id:
        # Mode dev : logger au lieu de print (meilleure traçabilité)
        logger.warning(f"[WA DEV] WhatsApp non configuré — message non envoyé à {to_phone}: {message[:100]}...")
        return {"status": "dev_mode", "message": message, "warning": "WhatsApp non configuré — message non envoyé"}

    url = f"{settings.wa_base_url}/{settings.wa_api_version}/{settings.wa_phone_id}/messages"

    headers = {
        "Authorization": f"Bearer {settings.wa_business_token}",
        "Content-Type": "application/json",
    }

    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to_phone,
        "type": "text",
        "text": {"body": message},
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(url, headers=headers, json=payload)
        response.raise_for_status()
        return response.json()


async def send_whatsapp_template(to_phone: str, template_name: str, language: str = "fr", components: list = None) -> dict:
    """Envoie un message via template WhatsApp approuvé."""
    if not settings.wa_business_token or not settings.wa_phone_id:
        logger.warning(f"[WA DEV] WhatsApp non configuré — template {template_name} non envoyé à {to_phone}")
        return {"status": "dev_mode", "template": template_name, "warning": "WhatsApp non configuré — message non envoyé"}

    url = f"{settings.wa_base_url}/{settings.wa_api_version}/{settings.wa_phone_id}/messages"

    headers = {
        "Authorization": f"Bearer {settings.wa_business_token}",
        "Content-Type": "application/json",
    }

    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to_phone,
        "type": "template",
        "template": {
            "name": template_name,
            "language": {"code": language},
        },
    }

    if components:
        payload["template"]["components"] = components

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(url, headers=headers, json=payload)
        response.raise_for_status()
        return response.json()
