"""AutoCommerce Clinic — Transcription des messages vocaux (assistant WhatsApp)

Rien ne transcrivait les messages vocaux jusqu'ici : un vocal arrivait
avec le contenu littéral "[Audio]" et ne déclenchait donc jamais aucune
intention côté assistant. Ce module télécharge le média WhatsApp et le
transcrit via Whisper (même clé OPENAI_API_KEY que facture_scanner.py).
"""
import logging

from config import get_settings
from core.openai_audio import transcribe_audio_bytes

logger = logging.getLogger(__name__)

# Whisper détecte automatiquement la langue (français, arabe standard,
# darija transcrite en graphie arabe...) — inutile de la forcer, une
# langue imposée dégraderait la reconnaissance si l'utilisateur switch.
_SUPPORTED_AUDIO_MIME_EXT = {
    "audio/aac": "aac",
    "audio/mp4": "mp4",
    "audio/mpeg": "mp3",
    "audio/amr": "amr",
    "audio/ogg": "ogg",
    "audio/opus": "ogg",
}


async def transcribe_whatsapp_voice(media_id: str) -> str | None:
    """Télécharge et transcrit un message vocal WhatsApp. Retourne le
    texte transcrit, ou None si la transcription échoue (config absente,
    fichier trop long, erreur API) — l'appelant doit alors informer
    poliment l'utilisateur plutôt que planter."""
    settings = get_settings()
    if getattr(settings, "env", "development") == "production" and (
        not getattr(settings, "whatsapp_enabled", False)
        or "whatsapp" not in settings.allowed_external_integrations
    ):
        logger.warning("Transcription vocale refusée par la politique des sorties externes")
        return None

    from services.omnicanal.whatsapp_connector import WhatsAppConnector

    connector = WhatsAppConnector()
    try:
        audio_bytes, mime_type = await connector.download_media(media_id)
    except Exception as e:
        logger.error(f"Échec du téléchargement du vocal {media_id}: {e}")
        return None

    ext = _SUPPORTED_AUDIO_MIME_EXT.get(mime_type, "ogg")

    try:
        text = await transcribe_audio_bytes(
            settings, audio_bytes, f"whatsapp-{media_id}.{ext}",
            budget_subject="whatsapp-voice",
        )
        logger.info("Vocal %s transcrit (%s caractères)", media_id, len(text))
        return text or None
    except Exception as e:
        logger.error(f"Échec de la transcription Whisper pour {media_id}: {e}")
        return None
