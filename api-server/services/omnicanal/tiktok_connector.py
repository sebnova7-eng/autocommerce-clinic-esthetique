"""
AutoCommerce Clinic — Connecteur TikTok Business Messaging (Bloc 1)
"""

import hashlib
import hmac
import json
import logging
import os
from typing import Optional

import httpx

from config import get_settings
from services.omnicanal.channel_adapter import ChannelAdapter

logger = logging.getLogger(__name__)
settings = get_settings()

TIKTOK_API_BASE = "https://business-api.tiktok.com/open_api/v1.3"


class TikTokConnector(ChannelAdapter):
    """Connecteur TikTok Business Messaging API."""

    CHANNEL_NAME = "tiktok"

    def _check_enabled(self) -> bool:
        """Vérifie si le canal est activé via feature flag. Retourne False si désactivé."""
        if not get_settings().tiktok_enabled:
            logger.error("TikTok channel is disabled via feature flag")
            return False
        return True

    @property
    def _access_token(self) -> str:
        return os.environ.get("TIKTOK_ACCESS_TOKEN", "")

    @property
    def _seller_id(self) -> str:
        return os.environ.get("TIKTOK_SELLER_ID", "")

    @property
    def _is_configured(self) -> bool:
        return bool(self._access_token and self._seller_id)

    async def send_message(self, contact_id: str, content: str,
                           template_name: Optional[str] = None,
                           template_params: Optional[dict] = None,
                           **kwargs) -> dict:
        if not self._check_enabled():
            return {"success": False, "status": "not_configured", "details": "Canal TikTok désactivé"}
        
        if not self._is_configured:
            return {
                "success": False,
                "external_message_id": None,
                "status": "not_configured",
                "details": "TikTok non configuré (partenariat requis)",
            }

        payload = {
            "seller_id": self._seller_id,
            "to_user_id": contact_id,
            "message": {"type": "text", "text": {"content": content}},
        }

        url = f"{TIKTOK_API_BASE}/message/send"
        headers = {
            "Authorization": f"Bearer {self._access_token}",
            "Content-Type": "application/json",
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(url, headers=headers, json=payload)
                response.raise_for_status()
                data = response.json()

            if data.get("code") == 0:
                return {
                    "success": True,
                    "external_message_id": data.get("data", {}).get("message_id"),
                    "status": "sent",
                    "details": data,
                }
            return {"success": False, "status": "failed", "details": data.get("message"), "external_message_id": None}
        except Exception as e:
            return {"success": False, "status": "failed", "details": str(e), "external_message_id": None}

    async def send_media(self, contact_id: str, media_type: str,
                         media_url: Optional[str] = None,
                         media_bytes: Optional[bytes] = None,
                         caption: Optional[str] = None,
                         **kwargs) -> dict:
        if not self._check_enabled():
            return {"success": False, "status": "not_configured", "details": "Canal TikTok désactivé"}
        return {"success": False, "status": "failed", "details": "Médias TikTok non supportés sans partenariat", "external_message_id": None}

    def verify_signature(self, raw_body: bytes, signature_header: str) -> bool:
        """Vérifie la signature TikTok. Utilise un secret dédié
        (TIKTOK_WEBHOOK_SECRET) — jamais le même que Meta
        (SOCIAL_WEBHOOK_SECRET) : ce sont deux fournisseurs distincts avec
        chacun leur propre clé de signature, les confondre revient à
        rejeter systématiquement les vrais webhooks TikTok."""
        secret = get_settings().tiktok_webhook_secret
        if not secret:
            return False
        expected = hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()
        return hmac.compare_digest(signature_header, expected)

    def parse_webhook_payload(self, raw_body: bytes) -> list[dict]:
        messages = []
        try:
            data = json.loads(raw_body)
            event = data.get("event", {})
            msg_data = event.get("message", {})
            if msg_data:
                messages.append({
                    "contact_id": msg_data.get("from_user_id", ""),
                    "contact_nom": None,
                    "content": msg_data.get("text", {}).get("content", ""),
                    "type_message": msg_data.get("type", "text"),
                    "direction": "entrant",
                    "media_url": None,
                    "external_message_id": msg_data.get("message_id"),
                    "timestamp": str(data.get("timestamp", "")),
                })
        except Exception:
            pass
        return messages

    async def get_channel_status(self) -> dict:
        if not get_settings().tiktok_enabled:
            return {"configured": True, "active": False, "status": "desactive", "details": "Désactivé par feature flag"}
            
        if not self._is_configured:
            return {"configured": False, "active": False, "status": "non_configure", "details": "TikTok non configuré"}
        
        return {"configured": True, "active": True, "status": "actif", "details": "TikTok Business API active"}

    async def check_delivery_status(self, external_message_id: str) -> dict:
        return {"status": "unknown", "updated_at": None, "details": "Via webhooks TikTok"}
