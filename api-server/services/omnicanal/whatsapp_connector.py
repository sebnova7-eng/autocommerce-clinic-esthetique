"""
AutoCommerce Clinic — Connecteur WhatsApp Meta Cloud API (Bloc 1)

Ce connecteur gère l'envoi de messages (texte/template) et de médias via l'API Graph de Meta.
Il implémente également la vérification des webhooks et le parsing des messages entrants.
"""

import hashlib
import hmac
import json
import logging
from typing import Optional
import asyncio

import httpx

from config import get_settings
from services.omnicanal.channel_adapter import ChannelAdapter

logger = logging.getLogger(__name__)
settings = get_settings()


# ── Types MIME WhatsApp ──────────────────────────────────

WA_MEDIA_TYPES = {
    "image": {"mime": "image/jpeg", "api_type": "image"},
    "video": {"mime": "video/mp4", "api_type": "video"},
    "audio": {"mime": "audio/aac", "api_type": "audio"},
    "pdf": {"mime": "application/pdf", "api_type": "document"},
    "document": {"mime": "application/octet-stream", "api_type": "document"},
    "location": {"mime": None, "api_type": "location"},
    "contact": {"mime": None, "api_type": "contacts"},
}


class WhatsAppConnector(ChannelAdapter):
    """Connecteur WhatsApp Meta Cloud API."""

    CHANNEL_NAME = "whatsapp"

    def __init__(self):
        self._settings = get_settings()
        self.base_url = self._settings.wa_base_url
        self.api_version = self._settings.wa_api_version
        self.phone_id = self._settings.wa_phone_id
        self.access_token = self._settings.wa_business_token
        self.webhook_verify_token = self._settings.wa_webhook_verify_token

    @property
    def webhook_secret(self) -> str:
        """Lit dynamiquement le secret webhook (supporte monkeypatch en tests)."""
        return get_settings().social_webhook_secret

    @property
    def _is_configured(self) -> bool:
        return bool(self.access_token and self.phone_id)

    @property
    def _messages_url(self) -> str:
        return f"{self.base_url}/{self.api_version}/{self.phone_id}/messages"

    # ── Envoi message ─────────────────────────────────────

    async def _request_with_retry(self, method: str, url: str, max_retries: int = 3, **kwargs) -> httpx.Response:
        """Exécute une requête HTTP avec retry exponentiel sur les erreurs 5xx."""
        async with httpx.AsyncClient(timeout=30.0) as client:
            for attempt in range(max_retries):
                try:
                    response = await client.request(method, url, **kwargs)
                    if response.status_code < 500:
                        return response
                    
                    logger.warning(f"WhatsApp API 5xx error (attempt {attempt+1}/{max_retries}): {response.status_code}")
                except (httpx.RequestError, httpx.TimeoutException) as e:
                    logger.warning(f"WhatsApp API request error (attempt {attempt+1}/{max_retries}): {e}")
                
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt  # 1s, 2s, 4s...
                    await asyncio.sleep(wait_time)
            
            # Si on arrive ici, on renvoie la dernière réponse ou on laisse l'exception
            return await client.request(method, url, **kwargs)

    async def download_media(self, media_id: str) -> tuple[bytes, str]:
        """Télécharge un média WhatsApp (image, audio...) par son ID Meta.

        Deux étapes côté API Graph : (1) résoudre l'URL de téléchargement
        signée à partir du media_id, (2) la récupérer avec le token
        d'accès. Retourne (contenu binaire, mime_type). Nécessaire pour
        transcrire les messages vocaux — rien ne le faisait jusqu'ici."""
        if not self._is_configured:
            raise RuntimeError("WhatsApp non configuré (WA_BUSINESS_TOKEN/WA_PHONE_ID manquants)")

        headers = {"Authorization": f"Bearer {self.access_token}"}
        meta_url = f"{self.base_url}/{self.api_version}/{media_id}"

        resp = await self._request_with_retry("GET", meta_url, headers=headers)
        resp.raise_for_status()
        info = resp.json()
        download_url = info.get("url")
        mime_type = info.get("mime_type", "application/octet-stream")
        if not download_url:
            raise RuntimeError(f"Impossible de résoudre l'URL du média {media_id}")

        file_resp = await self._request_with_retry("GET", download_url, headers=headers)
        file_resp.raise_for_status()
        return file_resp.content, mime_type

    async def send_message(self, contact_id: str, content: str,
                           template_name: Optional[str] = None,
                           template_params: Optional[list] = None,
                           **kwargs) -> dict:
        """Envoie un message WhatsApp (texte ou template).

        Correction B6 (AUDIT) : en production, NE JAMAIS renvoyer ``success=True``
        quand WA n'est pas configuré. Le précédent comportement « dev_mode »
        donnait l'illusion au patient que son message avait été envoyé alors
        qu'il était seulement journalisé. On lève une erreur explicite et
        le texte reste traçable en log.
        """
        if getattr(self._settings, "env", "development") == "production" and (
            not getattr(self._settings, "whatsapp_enabled", False)
            or "whatsapp" not in getattr(self._settings, "allowed_external_integrations", {"whatsapp"})
        ):
            raise RuntimeError("WhatsApp désactivé par la politique des intégrations externes")
        if not self._is_configured:
            logger.error(
                "WhatsApp non configuré — message NON envoyé à %s "
                "(clinic_id=%s, env=%s). Configurez WA_BUSINESS_TOKEN et "
                "WA_PHONE_ID ou positionnez explicitement WA_ALLOW_DEV_MODE=1 "
                "(uniquement hors production).",
                contact_id, getattr(self._settings, "clinic_id", "?"),
                getattr(self._settings, "env", "?"),
            )
            # En production : refus dur. Sinon : mode dev honnête (mais marqué).
            env = getattr(self._settings, "env", "development")
            allow_dev = getattr(self._settings, "wa_allow_dev_mode", False)
            if env == "production" and not allow_dev:
                raise RuntimeError(
                    "WhatsApp non configuré en production : WA_BUSINESS_TOKEN "
                    "et WA_PHONE_ID requis. Positionner WA_ALLOW_DEV_MODE=1 "
                    "uniquement pour staging/dev."
                )
            
            # En mode test ou si explicitement autorisé, on simule un succès pour ne pas bloquer les workflows
            is_success = (env == "test") or allow_dev
            
            return {
                "success": is_success,
                "external_message_id": f"mock_wa_{contact_id}" if is_success else None,
                "status": "dev_mode" if is_success else "failed_not_configured",
                "details": f"[WA DEV] à {contact_id}: {content[:100]}...",
            }

        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }

        if template_name:
            payload = {
                "messaging_product": "whatsapp",
                "recipient_type": "individual",
                "to": contact_id,
                "type": "template",
                "template": {
                    "name": template_name,
                    "language": {"code": "fr"},
                },
            }
            if template_params:
                # Meta attend des components: [{"type": "body", "parameters": [...]}]
                payload["template"]["components"] = [
                    {
                        "type": "body",
                        "parameters": [
                            {"type": "text", "text": str(p)} for p in template_params
                        ]
                    }
                ]
        else:
            payload = {
                "messaging_product": "whatsapp",
                "recipient_type": "individual",
                "to": contact_id,
                "type": "text",
                "text": {"body": content},
            }

        try:
            response = await self._request_with_retry("POST", self._messages_url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
            
            return {
                "success": True,
                "external_message_id": data.get("messages", [{}])[0].get("id"),
                "status": "sent",
                "details": data,
            }
        except Exception as e:
            logger.error(f"WhatsApp send_message failed: {e}")
            return {
                "success": False,
                "external_message_id": None,
                "status": "failed",
                "details": str(e),
            }

    async def send_media(self, contact_id: str, media_type: str,
                         media_url: Optional[str] = None,
                         media_bytes: Optional[bytes] = None,
                         caption: Optional[str] = None,
                         **kwargs) -> dict:
        """Envoie un média (image, PDF, etc.) via URL ou upload direct."""
        if getattr(self._settings, "env", "development") == "production" and (
            not getattr(self._settings, "whatsapp_enabled", False)
            or "whatsapp" not in getattr(self._settings, "allowed_external_integrations", {"whatsapp"})
        ):
            raise RuntimeError("WhatsApp désactivé par la politique des intégrations externes")
        if not self._is_configured:
            env = getattr(self._settings, "env", "development")
            allow_dev = getattr(self._settings, "wa_allow_dev_mode", False)
            if env == "production" and not allow_dev:
                raise RuntimeError("WhatsApp non configuré en production")
            return {
                "success": (env == "test") or allow_dev,
                "external_message_id": None,
                "status": "dev_mode",
                "details": f"[WA DEV] Média {media_type} à {contact_id}",
            }

        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }

        wa_type = WA_MEDIA_TYPES.get(media_type, WA_MEDIA_TYPES["document"])["api_type"]
        
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": contact_id,
            "type": wa_type,
            wa_type: {}
        }

        if media_url:
            payload[wa_type]["link"] = media_url
        elif media_bytes:
            # L'upload de média Meta est un flux en deux étapes (upload -> get id -> send id)
            # Pour simplifier dans ce bloc, on privilégie l'URL.
            return {
                "success": False,
                "status": "not_implemented",
                "details": "Upload direct de bytes non implémenté. Utilisez media_url.",
            }
        
        if caption and wa_type in ["image", "video", "document"]:
            payload[wa_type]["caption"] = caption

        try:
            response = await self._request_with_retry("POST", self._messages_url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
            
            return {
                "success": True,
                "external_message_id": data.get("messages", [{}])[0].get("id"),
                "status": "sent",
                "details": data,
            }
        except Exception as e:
            logger.error(f"WhatsApp send_media failed: {e}")
            return {
                "success": False,
                "external_message_id": None,
                "status": "failed",
                "details": str(e),
            }

    # ── Webhooks ──────────────────────────────────────────

    def verify_signature(self, raw_body: bytes, signature_header: str) -> bool:
        """Vérifie la signature X-Hub-Signature-256 de Meta."""
        if not self.webhook_secret or not signature_header:
            return False
        
        if signature_header.startswith("sha256="):
            signature_header = signature_header[7:]
            
        expected = hmac.new(
            self.webhook_secret.encode(),
            raw_body,
            hashlib.sha256
        ).hexdigest()
        
        return hmac.compare_digest(signature_header, expected)

    def parse_webhook_payload(self, raw_body: bytes) -> list[dict]:
        """Parse le JSON complexe de Meta pour extraire les messages."""
        messages = []
        try:
            data = json.loads(raw_body)
        except json.JSONDecodeError:
            return messages

        for entry in data.get("entry", []):
            for change in entry.get("changes", []):
                value = change.get("value", {})
                if "messages" in value:
                    for msg in value["messages"]:
                        # Protection contre contacts vide (arrive sur certains
                        # statuts de livraison / status messages de Meta).
                        contacts_list = value.get("contacts") or []
                        contact = contacts_list[0] if contacts_list else {}
                        
                        msg_type = msg.get("type")
                        content = ""
                        media_url = None
                        
                        if msg_type == "text":
                            content = msg.get("text", {}).get("body", "")
                        elif msg_type == "image":
                            content = "[Image]"
                            img_data = msg.get("image", {})
                            # Prioriser le lien direct, sinon l'ID Meta
                            media_url = img_data.get("link") or img_data.get("id")
                        elif msg_type == "video":
                            content = "[Video]"
                            media_url = msg.get("video", {}).get("id")
                        elif msg_type == "audio":
                            content = "[Audio]"
                            media_url = msg.get("audio", {}).get("id")
                        elif msg_type == "document":
                            content = "[Document]"
                            media_url = msg.get("document", {}).get("id")
                        elif msg_type == "location":
                            loc = msg.get("location", {})
                            content = f"Position : {loc.get('latitude', '')}, {loc.get('longitude', '')}"
                            media_url = None
                        elif msg_type == "button":
                            content = msg.get("button", {}).get("text", "")
                        elif msg_type == "interactive":
                            # Support list_reply ou button_reply
                            interactive = msg.get("interactive", {})
                            if interactive.get("type") == "button_reply":
                                content = interactive.get("button_reply", {}).get("title", "")
                            elif interactive.get("type") == "list_reply":
                                content = interactive.get("list_reply", {}).get("title", "")

                        messages.append({
                            "contact_id": msg.get("from"),
                            "contact_nom": contact.get("profile", {}).get("name"),
                            "content": content,
                            "type_message": msg_type,
                            "direction": "entrant",
                            "media_url": media_url,
                            "external_message_id": msg.get("id"),
                            "timestamp": msg.get("timestamp"),
                        })
        return messages

    async def get_channel_status(self) -> dict:
        """Vérifie si le canal est opérationnel."""
        if not self._is_configured:
            return {
                "configured": False,
                "active": False,
                "status": "non_configure",
                "details": "WhatsApp non configuré (token ou phone_id manquant)",
            }
        
        # On pourrait faire un appel léger à l'API Meta pour valider le token
        try:
            url = f"{self.base_url}/{self.api_version}/{self.phone_id}"
            headers = {"Authorization": f"Bearer {self.access_token}"}
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url, headers=headers)
                if response.status_code == 200:
                    return {
                        "configured": True,
                        "active": True,
                        "status": "actif",
                        "details": "WhatsApp Business API connectée",
                    }
                else:
                    return {
                        "configured": True,
                        "active": False,
                        "status": "erreur_auth",
                        "details": f"Erreur API Meta: {response.status_code}",
                    }
        except Exception as e:
            return {
                "configured": True,
                "active": False,
                "status": "indisponible",
                "details": f"Erreur connexion Meta: {e}",
            }

    async def check_delivery_status(self, external_message_id: str) -> dict:
        """Le statut est généralement reçu via webhook (sent, delivered, read)."""
        return {
            "status": "unknown",
            "updated_at": None,
            "details": "Le statut est mis à jour via webhooks entrants",
        }
