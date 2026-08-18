"""
AutoCommerce Clinic — Connecteurs Meta (Instagram + Facebook)

Instagram DM et Facebook Messenger partagent la même API Meta Graph.
Ce module fournit deux connecteurs séparés (pour clarté RBAC et logging)
mais réutilise la même couche réseau.

Restrictions :
  - Nécessitent un compte développeur Meta Business approuvé
  - Sans credentials configurées, retournent honnêtement "non configuré"
  - Instagram DM : messages limités à 7 jours après le dernier envoi
  - Facebook Messenger : fenêtre de 24h après le dernier message
"""

import hashlib
import hmac
import json
import os
import logging
from typing import Optional

import httpx

from config import get_settings
from services.omnicanal.channel_adapter import ChannelAdapter

logger = logging.getLogger(__name__)
settings = get_settings()


class _MetaBaseConnector(ChannelAdapter):
    """Base commune pour les connecteurs Meta (Instagram + Facebook)."""

    CHANNEL_NAME: str = ""

    def _check_enabled(self) -> bool:
        """Vérifie si le canal est activé via feature flag. Retourne False si désactivé."""
        enabled = False
        if self.CHANNEL_NAME == "instagram":
            enabled = get_settings().instagram_enabled
        elif self.CHANNEL_NAME == "facebook":
            enabled = get_settings().facebook_enabled
            
        if not enabled:
            logger.error(f"{self.CHANNEL_NAME} channel is disabled via feature flag")
            return False
        return True

    def _is_configured(self) -> bool:
        """Surcharge à définir dans les sous-classes."""
        return False

    @property
    def _access_token(self) -> str:
        return ""

    @property
    def _account_id(self) -> str:
        return ""

    @property
    def _messages_url(self) -> str:
        return ""

    async def send_message(self, contact_id: str, content: str,
                           template_name: Optional[str] = None,
                           template_params: Optional[dict] = None,
                           **kwargs) -> dict:
        if not self._check_enabled():
            return {"success": False, "status": "not_configured", "details": f"Canal {self.CHANNEL_NAME} désactivé"}
        if not self._is_configured:
            return {
                "success": False,
                "external_message_id": None,
                "status": "not_configured",
                "details": f"{self.CHANNEL_NAME} non connecté — configurez les credentials",
            }

        if template_name:
            payload = {
                "messaging_product": "instagram" if self.CHANNEL_NAME == "instagram" else "facebook",
                "recipient_type": "individual",
                "to": contact_id,
                "type": "template",
                "template": {
                    "name": template_name,
                    "language": {"code": "fr"},
                },
            }
            if template_params:
                payload["template"]["components"] = template_params
        else:
            payload = {
                "messaging_product": "instagram" if self.CHANNEL_NAME == "instagram" else "facebook",
                "recipient_type": "individual",
                "to": contact_id,
                "type": "text",
                "text": {"body": content},
            }

        return await self._send(payload)

    async def send_media(self, contact_id: str, media_type: str,
                         media_url: Optional[str] = None,
                         media_bytes: Optional[bytes] = None,
                         caption: Optional[str] = None,
                         **kwargs) -> dict:
        if not self._check_enabled():
            return {"success": False, "status": "not_configured", "details": f"Canal {self.CHANNEL_NAME} désactivé"}
        if not self._is_configured:
            return {
                "success": False,
                "external_message_id": None,
                "status": "not_configured",
                "details": f"{self.CHANNEL_NAME} non connecté",
            }
        if not media_url:
            return {"success": False, "status": "failed", "details": "media_url requis"}

        media_type_map = {
            "image": "image",
            "video": "video",
            "audio": "audio",
        }
        payload = {
            "messaging_product": "instagram" if self.CHANNEL_NAME == "instagram" else "facebook",
            "recipient_type": "individual",
            "to": contact_id,
            "type": media_type_map.get(media_type, "image"),
            media_type_map.get(media_type, "image"): {"link": media_url},
        }
        if caption:
            payload[media_type_map.get(media_type, "image")]["caption"] = caption

        return await self._send(payload)

    async def _send(self, payload: dict) -> dict:
        headers = {
            "Authorization": f"Bearer {self._access_token}",
            "Content-Type": "application/json",
        }
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(self._messages_url, headers=headers, json=payload)
                response.raise_for_status()
                data = response.json()

            external_id = data.get("messages", [{}])[0].get("id") if data.get("messages") else None
            return {
                "success": True,
                "external_message_id": external_id,
                "status": "sent",
                "details": data,
            }
        except httpx.HTTPStatusError as e:
            return {"success": False, "status": "failed", "details": str(e), "external_message_id": None}
        except Exception as e:
            return {"success": False, "status": "failed", "details": f"Erreur: {e}", "external_message_id": None}

    def verify_signature(self, raw_body: bytes, signature_header: str) -> bool:
        """Vérifie X-Hub-Signature-256 (Meta standard)."""
        if not get_settings().social_webhook_secret:
            return False
        hex_hash = signature_header
        if signature_header.startswith("sha256="):
            hex_hash = signature_header[len("sha256="):]
        expected = hmac.new(
            get_settings().social_webhook_secret.encode(),
            raw_body,
            hashlib.sha256,
        ).hexdigest()
        return hmac.compare_digest(hex_hash, expected)

    def parse_webhook_payload(self, raw_body: bytes) -> list[dict]:
        """Parse webhook Meta (Instagram/Facebook)."""
        messages = []
        try:
            data = json.loads(raw_body)
        except (json.JSONDecodeError, UnicodeDecodeError):
            return messages

        if data.get("object") not in ("instagram", "page"):
            return messages

        for entry in data.get("entry", []):
            for messaging in entry.get("messaging", []):
                sender = messaging.get("sender", {}).get("id", "")
                message = messaging.get("message", {})
                text = message.get("text", "")
                msg_type = "text" if text else "media"
                attachments = message.get("attachments", [])
                media_url = attachments[0].get("payload", {}).get("url") if attachments else None

                messages.append({
                    "contact_id": sender,
                    "contact_nom": None,
                    "content": text or "[Média]",
                    "type_message": msg_type,
                    "direction": "entrant",
                    "media_url": media_url,
                    "external_message_id": message.get("mid"),
                    "timestamp": str(messaging.get("timestamp", "")),
                })

        return messages

    async def get_channel_status(self) -> dict:
        enabled = False
        if self.CHANNEL_NAME == "instagram":
            enabled = get_settings().instagram_enabled
        elif self.CHANNEL_NAME == "facebook":
            enabled = get_settings().facebook_enabled

        if not enabled:
            return {"configured": True, "active": False, "status": "desactive", "details": "Désactivé par feature flag"}

        if not self._is_configured:
            return {
                "configured": False, "active": False, "limited": False,
                "status": "non_configure",
                "details": f"{self.CHANNEL_NAME} non configuré — configurez les credentials",
            }
        try:
            headers = {"Authorization": f"Bearer {self._access_token}"}
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(self._account_id, headers=headers)
                response.raise_for_status()
            return {
                "configured": True, "active": True, "limited": False,
                "status": "actif",
                "details": f"{self.CHANNEL_NAME} actif",
            }
        except Exception as e:
            return {
                "configured": True, "active": False, "limited": False,
                "status": "configure",
                "details": f"Configuré mais API inaccessible: {e}",
            }

    async def check_delivery_status(self, external_message_id: str) -> dict:
        return {
            "status": "unknown",
            "updated_at": None,
            "details": f"Statut disponible via webhooks {self.CHANNEL_NAME}",
        }


class InstagramConnector(_MetaBaseConnector):
    """Connecteur Instagram Direct Messages."""
    CHANNEL_NAME = "instagram"

    def _is_configured(self) -> bool:
        return bool(os.environ.get("INSTAGRAM_ACCESS_TOKEN"))

    @property
    def _access_token(self) -> str:
        return os.environ.get("INSTAGRAM_ACCESS_TOKEN", "")

    @property
    def _account_id(self) -> str:
        return os.environ.get("INSTAGRAM_BUSINESS_ACCOUNT_ID", "")

    @property
    def _messages_url(self) -> str:
        account_id = self._account_id
        return f"{get_settings().wa_base_url}/{get_settings().wa_api_version}/{account_id}/messages"


class FacebookConnector(_MetaBaseConnector):
    """Connecteur Facebook Messenger."""
    CHANNEL_NAME = "facebook"

    def _is_configured(self) -> bool:
        return bool(os.environ.get("FACEBOOK_ACCESS_TOKEN"))

    @property
    def _access_token(self) -> str:
        return os.environ.get("FACEBOOK_ACCESS_TOKEN", "")

    @property
    def _account_id(self) -> str:
        return os.environ.get("FACEBOOK_PAGE_ID", "")

    @property
    def _messages_url(self) -> str:
        page_id = self._account_id
        return f"{get_settings().wa_base_url}/{get_settings().wa_api_version}/{page_id}/messages"
