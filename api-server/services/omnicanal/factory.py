"""
AutoCommerce Clinic — Factory de connecteurs omnicanal (Bloc 1)

Gère l'instanciation dynamique des connecteurs à partir du canal demandé.
"""

import importlib
import logging
from typing import Optional, Dict, List

from services.omnicanal.channel_adapter import ChannelAdapter
from services.omnicanal import get_connector_registry

logger = logging.getLogger(__name__)

# Cache singleton partagé
_connector_cache: Dict[str, ChannelAdapter] = {}


class OmnicanalFactory:
    """Factory singleton pour les connecteurs omnicanaux."""

    def get_connector(self, canal: str) -> Optional[ChannelAdapter]:
        """Retourne une instance du connecteur pour le canal demandé."""
        if canal in _connector_cache:
            return _connector_cache[canal]

        registry = get_connector_registry()
        class_path = registry.get(canal)
        if not class_path:
            return None

        try:
            module_path, class_name = class_path.rsplit(".", 1)
            module = importlib.import_module(module_path)
            connector_class = getattr(module, class_name)
            instance = connector_class()
            _connector_cache[canal] = instance
            return instance
        except (ImportError, AttributeError) as e:
            logger.error(f"Erreur chargement connecteur {canal}: {e}")
            return None

    def get_all_connectors(self) -> List[str]:
        """Retourne la liste des noms de canaux supportés."""
        return list(get_connector_registry().keys())

    @staticmethod
    def clear_cache():
        """Vide le cache des connecteurs (utile en tests)."""
        global _connector_cache
        _connector_cache = {}


# Fonctions helper pour compatibilité avec l'existant
def get_connector(canal: str) -> Optional[ChannelAdapter]:
    return OmnicanalFactory().get_connector(canal)

def get_all_connectors() -> Dict[str, ChannelAdapter]:
    factory = OmnicanalFactory()
    registry = get_connector_registry()
    return {canal: factory.get_connector(canal) for canal in registry if factory.get_connector(canal)}

def clear_cache():
    OmnicanalFactory.clear_cache()

def get_canal_labels() -> dict:
    """Retourne les labels, couleurs et icônes de chaque canal."""
    return {
        "whatsapp": {
            "label": "WhatsApp Business",
            "color": "#25D366",
            "icon": "whatsapp",
            "limitations": "1000 messages/jour (sandbox), 24h fenêtre conversation",
            "config_required": ["WA_BUSINESS_TOKEN", "WA_PHONE_ID"],
        },
        "instagram": {
            "label": "Instagram DM",
            "color": "#E4405F",
            "icon": "instagram",
            "limitations": "Messages uniquement aux abonnés ou en réponse",
            "config_required": ["INSTAGRAM_ACCESS_TOKEN"],
        },
        "facebook": {
            "label": "Facebook Messenger",
            "color": "#0084FF",
            "icon": "facebook",
            "limitations": "Fenêtre 7 jours après dernier message patient",
            "config_required": ["FACEBOOK_ACCESS_TOKEN"],
        },
        "tiktok": {
            "label": "TikTok Messages",
            "color": "#000000",
            "icon": "tiktok",
            "limitations": "Messages uniquement en réponse (< 72h)",
            "config_required": ["TIKTOK_ACCESS_TOKEN", "TIKTOK_SELLER_ID"],
        },
        "email": {
            "label": "Email",
            "color": "#EA4335",
            "icon": "email",
            "limitations": "Aucune",
            "config_required": ["RESEND_API_KEY"],
        },
        "sms": {
            "label": "SMS",
            "color": "#FFC107",
            "icon": "sms",
            "limitations": "160 caractères max, coût par SMS",
            "config_required": ["TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN", "TWILIO_FROM"],
        },
    }
