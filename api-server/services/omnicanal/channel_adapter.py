"""
AutoCommerce Clinic — ChannelAdapter (Bloc 1)

Interface commune (Abstract Base Class) que chaque connecteur de canal
doit implémenter. Permet d'ajouter de nouveaux canaux (Email, SMS, etc.)
sans modifier la logique métier du CRM.

Contrats :
  - send_message : envoie un message sortant, retourne un dict standardisé
  - send_media   : envoie une pièce jointe
  - verify_signature : vérifie la signature d'un webhook entrant
  - parse_webhook_payload : transforme un payload brut en dict normalisé
  - get_channel_status : retourne l'état du canal (configuré / limité / etc.)

Chaque connecteur retourne un résultat standardisé :
  {
    "success": bool,
    "external_message_id": str | None,
    "status": "sent" | "failed" | "queued" | "not_configured",
    "details": str | dict,
    "delivery_status": "sent" | "delivered" | "read" | None,
  }
"""

from abc import ABC, abstractmethod
from typing import Optional


class ChannelAdapter(ABC):
    """Interface abstraite pour un connecteur de canal."""

    # Nom unique du canal (doit correspondre à CanalEnum)
    CHANNEL_NAME: str = ""

    @abstractmethod
    async def send_message(self, contact_id: str, content: str,
                           template_name: Optional[str] = None,
                           template_params: Optional[dict] = None,
                           **kwargs) -> dict:
        """Envoie un message texte ou template.
        
        Args:
            contact_id: Identifiant externe du destinataire
            content: Contenu texte du message
            template_name: Nom du template (optionnel, pour WhatsApp templates)
            template_params: Paramètres du template (optionnel)

        Returns:
            Dict standardisé avec keys: success, external_message_id, status, details
        """
        ...

    @abstractmethod
    async def send_media(self, contact_id: str, media_type: str,
                         media_url: Optional[str] = None,
                         media_bytes: Optional[bytes] = None,
                         caption: Optional[str] = None,
                         **kwargs) -> dict:
        """Envoie une pièce jointe (image, vidéo, PDF, audio, etc.).
        
        Args:
            contact_id: Identifiant externe du destinataire
            media_type: "image" | "video" | "audio" | "pdf" | "document" | "location" | "contact"
            media_url: URL publique du média (prioritaire si fourni)
            media_bytes: Contenu binaire du média (upload direct)
            caption: Légende optionnelle

        Returns:
            Dict standardisé
        """
        ...

    @abstractmethod
    def verify_signature(self, raw_body: bytes, signature_header: str) -> bool:
        """Vérifie la signature HMAC du webhook entrant.
        
        Args:
            raw_body: Corps brut de la requête HTTP
            signature_header: Valeur de l'en-tête de signature

        Returns:
            True si la signature est valide
        """
        ...

    @abstractmethod
    def parse_webhook_payload(self, raw_body: bytes) -> list[dict]:
        """Parse le payload brut du webhook en liste de messages normalisés.
        
        Chaque message normalisé doit contenir :
            - contact_id: str
            - contact_nom: str | None
            - content: str | None
            - type_message: str (texte, image, etc.)
            - direction: "entrant" (toujours pour un webhook)
            - media_url: str | None
            - external_message_id: str | None
            - timestamp: str | None

        Args:
            raw_body: Corps brut de la requête HTTP

        Returns:
            Liste de dicts normalisés
        """
        ...

    @abstractmethod
    async def get_channel_status(self) -> dict:
        """Retourne l'état du canal.
        
        Returns:
            {
                "configured": bool,
                "active": bool,
                "limited": bool,
                "status": "non_configure" | "configure" | "actif" | "limite",
                "details": str,
            }
        """
        ...

    @abstractmethod
    async def check_delivery_status(self, external_message_id: str) -> dict:
        """Vérifie le statut de livraison d'un message envoyé.
        
        Args:
            external_message_id: ID retourné par le canal lors de l'envoi

        Returns:
            {
                "status": "sent" | "delivered" | "read" | "failed",
                "updated_at": str | None,
            }
        """
        ...
