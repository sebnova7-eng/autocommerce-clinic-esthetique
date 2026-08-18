"""Passerelle contrôlée pour les appels audio OpenAI/Whisper."""

from __future__ import annotations

import asyncio
import os
import tempfile
from typing import Any

from core.llm_budget import reserve_budget
from core.medical_ai_policy import require_medical_ai_approval


async def transcribe_audio_bytes(
    settings: Any,
    audio_bytes: bytes,
    filename: str,
    *,
    language: str | None = None,
    budget_subject: str = "audio",
    budget_clinic_id: int | None = None,
    medical_data: bool = False,
) -> str:
    """Transcrit un audio après contrôle de politique et réservation de quota.

    Le SDK synchrone est isolé dans un thread afin de ne pas bloquer la boucle
    FastAPI/Celery. Les octets ne sont jamais journalisés.
    """
    if medical_data:
        require_medical_ai_approval(settings, "audio_transcription")

    if getattr(settings, "env", "development") == "production" and (
        not getattr(settings, "llm_enabled", False)
        or "ai" not in settings.allowed_external_integrations
        or getattr(settings, "llm_provider", "openai") != "openai"
    ):
        raise RuntimeError("Transcription IA désactivée par la politique des sorties externes")
    api_key = getattr(settings, "openai_api_key", "")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY absent")
    if len(audio_bytes) > 25 * 1024 * 1024:
        raise ValueError("Audio trop volumineux (maximum 25 Mo)")

    await reserve_budget(
        settings,
        budget_subject,
        500,
        clinic_id=budget_clinic_id,
    )

    fd, path = tempfile.mkstemp(prefix="autocommerce-audio-", suffix=os.path.splitext(filename)[1])
    os.close(fd)
    try:
        with open(path, "wb") as handle:
            handle.write(audio_bytes)

        def _call_sync():
            from openai import OpenAI
            client = OpenAI(api_key=api_key)
            with open(path, "rb") as audio_file:
                kwargs = {"model": "whisper-1", "file": audio_file}
                if language:
                    kwargs["language"] = language
                return client.audio.transcriptions.create(**kwargs)

        result = await asyncio.to_thread(_call_sync)
        return (result.text or "").strip()
    finally:
        try:
            os.remove(path)
        except FileNotFoundError:
            pass
