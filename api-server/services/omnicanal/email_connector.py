"""
AutoCommerce Clinic — Connecteur Email (Bloc 1)

Supporte Resend.com via API HTTP.
"""

import logging
from typing import Optional

import httpx

from config import get_settings
from services.omnicanal.channel_adapter import ChannelAdapter

logger = logging.getLogger(__name__)
settings = get_settings()


class EmailConnector(ChannelAdapter):
    """Connecteur Email via Resend API."""

    CHANNEL_NAME = "email"

    @property
    def _resend_key(self) -> str:
        return get_settings().resend_api_key

    @property
    def _is_configured(self) -> bool:
        return bool(self._resend_key)

    async def send_message(self, contact_id: str, content: str,
                           template_name: Optional[str] = None,
                           template_params: Optional[dict] = None,
                           subject: Optional[str] = None,
                           **kwargs) -> dict:
        """Envoie un email via Resend."""
        if not self._is_configured:
            return {
                "success": False,
                "external_message_id": None,
                "status": "not_configured",
                "details": "Email non configuré — configurez RESEND_API_KEY",
            }

        from_addr = get_settings().smtp_from
        
        payload = {
            "from": from_addr,
            "to": [contact_id],
            "subject": subject or "Message de votre clinique",
        }

        if template_name:
            # Resend supporte des templates via leur API ou via rendu local
            # Ici on simule l'usage de template_id si fourni
            payload["template_id"] = template_name
            if template_params:
                payload["params"] = template_params
        else:
            # Conversion simple texte -> HTML si nécessaire
            html_content = content.replace("\n", "<br>")
            payload["html"] = f"<div>{html_content}</div>"

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    "https://api.resend.com/emails",
                    headers={
                        "Authorization": f"Bearer {self._resend_key}",
                        "Content-Type": "application/json"
                    },
                    json=payload,
                )
                response.raise_for_status()
                data = response.json()
                
            return {
                "success": True,
                "external_message_id": data.get("id"),
                "status": "sent",
                "details": data,
            }
        except httpx.HTTPStatusError as e:
            logger.error(f"Resend API error: {e.response.text}")
            return {"success": False, "status": "failed", "details": f"Resend error: {e.response.text}", "external_message_id": None}
        except Exception as e:
            logger.error(f"Email send failed: {e}")
            return {"success": False, "status": "failed", "details": str(e), "external_message_id": None}

    async def send_media(self, contact_id: str, media_type: str,
                         media_url: Optional[str] = None,
                         media_bytes: Optional[bytes] = None,
                         caption: Optional[str] = None,
                         **kwargs) -> dict:
        """Envoi de pièces jointes via Resend."""
        if not self._is_configured:
            return {"success": False, "status": "not_configured", "details": "Email non configuré", "external_message_id": None}
        
        # Resend attend un champ 'attachments' : [{"filename": "...", "content": "base64..."} ou {"path": "url"}]
        # Implémentation simplifiée via URL
        if not media_url:
            return {"success": False, "status": "failed", "details": "media_url requis pour les pièces jointes email", "external_message_id": None}

        from_addr = get_settings().smtp_from
        payload = {
            "from": from_addr,
            "to": [contact_id],
            "subject": caption or "Document de votre clinique",
            "html": f"<p>{caption or 'Veuillez trouver ci-joint votre document.'}</p>",
            "attachments": [
                {"path": media_url, "filename": media_url.split("/")[-1]}
            ]
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    "https://api.resend.com/emails",
                    headers={
                        "Authorization": f"Bearer {self._resend_key}",
                        "Content-Type": "application/json"
                    },
                    json=payload,
                )
                response.raise_for_status()
                data = response.json()
            return {"success": True, "external_message_id": data.get("id"), "status": "sent", "details": data}
        except Exception as e:
            return {"success": False, "status": "failed", "details": str(e), "external_message_id": None}

    def verify_signature(self, raw_body: bytes, signature_header: str) -> bool:
        return False

    def parse_webhook_payload(self, raw_body: bytes) -> list[dict]:
        return []

    async def get_channel_status(self) -> dict:
        if not self._is_configured:
            return {
                "configured": False, "active": False, "status": "non_configure",
                "details": "Email non configuré — RESEND_API_KEY manquante",
            }
        return {
            "configured": True, "active": True, "status": "actif",
            "details": "Email (Resend) configuré",
        }

    async def check_delivery_status(self, external_message_id: str) -> dict:
        return {"status": "unknown", "updated_at": None, "details": "Statut via webhooks Resend"}
