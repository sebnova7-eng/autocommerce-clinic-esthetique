"""Politique fail-closed pour les flux contenant des données médicales.

Le frontend ne peut jamais activer cette politique : elle est résolue uniquement
à partir des Settings backend injectés au démarrage.
"""

from __future__ import annotations

from typing import Any


class MedicalAIBlocked(RuntimeError):
    """Un flux médical externe n’est pas explicitement autorisé."""


def require_medical_ai_approval(settings: Any, operation: str) -> None:
    """Autorise un appel médical externe uniquement en mode explicitement approuvé.

    Le défaut est bloquant. L’approbation doit être activée côté serveur et
    rester cohérente avec le gate LLM général et l’allowlist de providers.
    """
    if not bool(getattr(settings, "medical_ai_provider_approved", False)):
        raise MedicalAIBlocked(
            f"Flux médical externe bloqué : MEDICAL_AI_PROVIDER_APPROVED=false ({operation})"
        )

    provider = str(getattr(settings, "llm_provider", "openai") or "").lower()
    allowlist = {
        item.strip().lower()
        for item in str(getattr(settings, "llm_provider_allowlist", "")).split(",")
        if item.strip()
    }
    if not getattr(settings, "llm_enabled", False):
        raise MedicalAIBlocked(f"Flux médical bloqué : LLM_ENABLED=false ({operation})")
    if "ai" not in getattr(settings, "allowed_external_integrations", set()):
        raise MedicalAIBlocked(f"Flux médical bloqué : intégration AI non autorisée ({operation})")
    if provider not in allowlist:
        raise MedicalAIBlocked(f"Flux médical bloqué : provider non allowlisté ({provider})")
    if provider == "openai" and not str(getattr(settings, "openai_api_key", "")).strip():
        raise MedicalAIBlocked(f"Flux médical bloqué : clé OpenAI absente ({operation})")


def should_store_raw_medical_transcription(settings: Any) -> bool:
    """Retourne la décision de conservation brute, false par défaut."""
    return bool(getattr(settings, "medical_ai_store_raw_transcription", False))
