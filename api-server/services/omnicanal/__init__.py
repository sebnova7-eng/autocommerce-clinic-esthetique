"""
AutoCommerce Clinic — Connecteurs de canaux omnicanal (Bloc 1)

Registry des connecteurs disponibles. Chaque connecteur implémente
l'interface ChannelAdapter. Les connecteurs non configurés retournent
honnêtement "non configuré" sans faux succès.
"""

from services.omnicanal.channel_adapter import ChannelAdapter as ChannelAdapter  # noqa: F401 (re-export)


def get_connector_registry() -> dict[str, str]:
    """Retourne le registre des connecteurs disponibles.
    
    Les connecteurs sont importés de manière lazy pour éviter
    les dépendances circulaires et permettre l'ajout de nouveaux
    connecteurs sans modifier ce fichier (via le registre dynamique).
    """
    return {
        "whatsapp": "services.omnicanal.whatsapp_connector.WhatsAppConnector",
        "instagram": "services.omnicanal.meta_connector.InstagramConnector",
        "facebook": "services.omnicanal.meta_connector.FacebookConnector",
        "tiktok": "services.omnicanal.tiktok_connector.TikTokConnector",
        "email": "services.omnicanal.email_connector.EmailConnector",
        "sms": "services.omnicanal.sms_connector.SMSConnector",
    }


def get_canal_labels() -> dict[str, dict]:
    """Retourne les métadonnées de chaque canal."""
    return {
        "whatsapp": {
            "label": "WhatsApp",
            "icon": "message-circle",
            "color": "#25D366",
            "config_required": ["WA_BUSINESS_TOKEN", "WA_PHONE_ID"],
            "limitations": "Fenêtre de 24h après le dernier message du client (hors templates approuvés)",
        },
        "instagram": {
            "label": "Instagram DM",
            "icon": "instagram",
            "color": "#E1306C",
            "config_required": ["INSTAGRAM_ACCESS_TOKEN", "INSTAGRAM_BUSINESS_ACCOUNT_ID"],
            "limitations": "Nécessite un compte développeur Meta Business approuvé. Messages limités à 7 jours.",
        },
        "facebook": {
            "label": "Facebook Messenger",
            "icon": "facebook",
            "color": "#0084FF",
            "config_required": ["FACEBOOK_ACCESS_TOKEN", "FACEBOOK_PAGE_ID"],
            "limitations": "Nécessite un compte développeur Meta Business. Fenêtre de 24h.",
        },
        "tiktok": {
            "label": "TikTok Business",
            "icon": "music",
            "color": "#000000",
            "config_required": ["TIKTOK_ACCESS_TOKEN", "TIKTOK_SELLER_ID"],
            "limitations": "API TikTok Business Messaging très restrictive. Nécessite un compte Business TikTok validé et un partenariat officiel. Contact commercial TikTok obligatoire.",
        },
        "email": {
            "label": "Email",
            "icon": "mail",
            "color": "#3B82F6",
            "config_required": ["SMTP_HOST", "SMTP_PORT", "SMTP_USER", "SMTP_PASSWORD"],
            "limitations": "Configurable via Resend ou SMTP standard. Nécessite un domaine vérifié.",
        },
        "sms": {
            "label": "SMS",
            "icon": "smartphone",
            "color": "#10B981",
            "config_required": ["TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN", "TWILIO_FROM_NUMBER"],
            "limitations": "Configurable via Twilio ou fournisseur SMS local. Coût par message.",
        },
    }
