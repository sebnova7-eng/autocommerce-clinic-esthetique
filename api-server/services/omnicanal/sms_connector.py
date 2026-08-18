"""
AutoCommerce Clinic — Connecteur SMS via Twilio (Bloc 1)
"""

import logging
from typing import Optional
from urllib.parse import parse_qs

import httpx

from config import get_settings
from services.omnicanal.channel_adapter import ChannelAdapter

logger = logging.getLogger(__name__)
settings = get_settings()


class SMSConnector(ChannelAdapter):
    """Connecteur SMS via Twilio API."""

    CHANNEL_NAME = "sms"

    @property
    def _sid(self) -> str:
        return get_settings().twilio_account_sid

    @property
    def _token(self) -> str:
        return get_settings().twilio_auth_token

    @property
    def _from(self) -> str:
        return get_settings().twilio_from

    @property
    def _is_configured(self) -> bool:
        return bool(self._sid and self._token and self._from)

    async def send_message(self, contact_id: str, content: str,
                           template_name: Optional[str] = None,
                           template_params: Optional[dict] = None,
                           **kwargs) -> dict:
        """Envoie un SMS via Twilio REST API."""
        if not self._is_configured:
            return {
                "success": False,
                "external_message_id": None,
                "status": "not_configured",
                "details": "SMS non configuré — configurez TWILIO_ACCOUNT_SID, AUTH_TOKEN et FROM",
            }

        url = f"https://api.twilio.com/2010-04-01/Accounts/{self._sid}/Messages.json"

        # SMS ne supporte pas nativement les templates complexes comme WhatsApp,
        # on fait un rendu simple si template_name est fourni.
        final_content = content
        if template_name and template_params:
            try:
                # Simulation de rendu de template
                from config import WA_TEMPLATES
                tpl = WA_TEMPLATES.get(template_name, content)
                final_content = tpl.format(**template_params)
            except Exception:
                final_content = content

        try:
            async with httpx.AsyncClient(timeout=30.0, auth=(self._sid, self._token)) as client:
                response = await client.post(url, data={
                    "From": self._from,
                    "To": contact_id,
                    "Body": final_content[:1600],
                })
                response.raise_for_status()
                data = response.json()

            return {
                "success": True,
                "external_message_id": data.get("sid"),
                "status": "sent",
                "details": data,
            }
        except httpx.HTTPStatusError as e:
            logger.error(f"Twilio API error: {e.response.text}")
            return {"success": False, "status": "failed", "details": f"Twilio error: {e.response.text}", "external_message_id": None}
        except Exception as e:
            logger.error(f"SMS send failed: {e}")
            return {"success": False, "status": "failed", "details": str(e), "external_message_id": None}

    async def send_media(self, contact_id: str, media_type: str,
                         media_url: Optional[str] = None,
                         media_bytes: Optional[bytes] = None,
                         caption: Optional[str] = None,
                         **kwargs) -> dict:
        """Envoi de MMS via Twilio (si supporté par le numéro)."""
        if not self._is_configured:
            return {"success": False, "status": "not_configured", "details": "SMS non configuré", "external_message_id": None}
        
        if not media_url:
            return {"success": False, "status": "failed", "details": "media_url requis pour MMS", "external_message_id": None}

        url = f"https://api.twilio.com/2010-04-01/Accounts/{self._sid}/Messages.json"
        
        try:
            async with httpx.AsyncClient(timeout=30.0, auth=(self._sid, self._token)) as client:
                response = await client.post(url, data={
                    "From": self._from,
                    "To": contact_id,
                    "Body": caption or "",
                    "MediaUrl": media_url
                })
                response.raise_for_status()
                data = response.json()
            return {"success": True, "external_message_id": data.get("sid"), "status": "sent", "details": data}
        except Exception as e:
            return {"success": False, "status": "failed", "details": str(e), "external_message_id": None}

    def verify_signature(self, raw_body: bytes, signature_header: str) -> bool:
        """Twilio ne signe PAS le corps brut en HMAC-SHA256 : sa signature
        réelle est base64(HMAC-SHA1(URL_complète + paramètres_form_triés,
        Auth Token)) — un algorithme entièrement différent de celui utilisé
        ici auparavant, qui ne validera jamais un vrai webhook Twilio.

        Plutôt que de garder un faux positif/négatif qui donne l'illusion
        d'une vérification, on refuse explicitement tant que le vrai
        algorithme n'est pas implémenté (nécessite l'URL complète de la
        requête, pas seulement le corps — voir middleware/webhook_omnicanal.py
        si cette intégration devient prioritaire)."""
        logger.error(
            "SMS/Twilio verify_signature non implémenté (algorithme Twilio réel "
            "requis, pas HMAC-SHA256 générique) — webhook refusé par sécurité."
        )
        return False

    def parse_webhook_payload(self, raw_body: bytes) -> list[dict]:
        """Parse le form-data de Twilio."""
        messages = []
        try:
            body = raw_body.decode("utf-8")
            params = parse_qs(body)
            
            if "Body" in params:
                messages.append({
                    "contact_id": params.get("From", [""])[0],
                    "contact_nom": None,
                    "content": params.get("Body", [""])[0],
                    "type_message": "text",
                    "direction": "entrant",
                    "media_url": params.get("MediaUrl0", [None])[0],
                    "external_message_id": params.get("MessageSid", [""])[0],
                    "timestamp": None,
                })
        except Exception:
            pass
        return messages

    async def get_channel_status(self) -> dict:
        if not self._is_configured:
            return {
                "configured": False, "active": False, "status": "non_configure",
                "details": "SMS non configuré (SID/Token/From manquant)",
            }
        return {
            "configured": True, "active": True, "status": "actif",
            "details": "SMS (Twilio) opérationnel",
        }

    async def check_delivery_status(self, external_message_id: str) -> dict:
        return {"status": "unknown", "updated_at": None, "details": "Statut via webhooks Twilio"}
