from __future__ import annotations

import asyncio
import hashlib
import json
import time
from datetime import datetime, timezone
from typing import Any

from config import get_settings
from core.llm_budget import LLMBudgetExceeded
from core.llm_client import LLMResponse, LLMUnavailable, get_llm_client, cache_clear, reset_llm_client


SYNTHETIC_CLINIC_ID = 9981
SYNTHETIC_SUBJECT = "clinic:9981:synthetic-provider-validation:user:1"
SYNTHETIC_PROMPT = "Respond with exactly the single word SYNTHETIC_OK."


def base_settings() -> Any:
    settings = get_settings()
    return settings.model_copy(update={
        "env": "production",
        "llm_enabled": True,
        "external_integrations_allowlist": "ai",
        "llm_provider": "openai",
        "llm_provider_allowlist": "openai",
        "llm_max_requests_per_user_day": 100,
        "llm_daily_token_budget": 100_000,
        "llm_monthly_token_budget": 1_000_000,
        "llm_max_requests_per_clinic_day": 1_000,
    })


def common_metadata(settings: Any) -> dict[str, Any]:
    message_sha256 = hashlib.sha256(SYNTHETIC_PROMPT.encode("utf-8")).hexdigest()
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "provider": "openai",
        "endpoint": "https://api.openai.com/v1/chat/completions",
        "model": settings.openai_model,
        "api_key_present": bool(settings.openai_api_key),
        "synthetic_only": True,
        "phi_present": False,
        "patient_id_present": False,
        "message_roles": ["system", "user"],
        "message_character_counts": [
            len("Return only the requested synthetic validation token."),
            len(SYNTHETIC_PROMPT),
        ],
        "message_sha256": message_sha256,
        "request_parameters": {
            "temperature": 0.0,
            "max_tokens": 16,
            "stream": False,
            "response_format_json": False,
        },
    }


async def main() -> None:
    settings = base_settings()
    cache_clear()
    result: dict[str, Any] = common_metadata(settings)
    if not settings.openai_api_key:
        result.update({
            "status": "OPENAI_PROVIDER_NOT_VALIDATED",
            "detail": "OPENAI_API_KEY absent dans le conteneur staging",
        })
        print(json.dumps(result, ensure_ascii=False, indent=2))
        raise SystemExit(2)

    client = get_llm_client(settings)
    messages = [
        {"role": "system", "content": "Return only the requested synthetic validation token."},
        {"role": "user", "content": SYNTHETIC_PROMPT},
    ]
    started = time.perf_counter()
    response = await client.chat(
        messages,
        model=settings.openai_model,
        temperature=0.0,
        max_tokens=16,
        use_cache=False,
        budget_subject=SYNTHETIC_SUBJECT,
        budget_clinic_id=SYNTHETIC_CLINIC_ID,
    )
    wall_latency_ms = round((time.perf_counter() - started) * 1000, 2)
    result["wall_latency_ms"] = wall_latency_ms

    if isinstance(response, LLMResponse):
        result.update({
            "status": "PROVIDER_PASS",
            "response_provider": response.provider,
            "response_model": response.model,
            "response_latency_ms": response.latency_ms,
            "usage": response.usage,
            "response_character_count": len(response.text),
            "response_sha256": hashlib.sha256(response.text.encode("utf-8")).hexdigest(),
        })
    else:
        result.update({
            "status": "PROVIDER_FAIL",
            "response_provider": response.provider,
            "detail": response.reason,
        })

    await client.aclose()
    await reset_llm_client()
    quota_settings = settings.model_copy(update={"llm_max_requests_per_clinic_day": 1})
    quota_client = get_llm_client(quota_settings)
    quota_response = await quota_client.chat(
        messages,
        model=settings.openai_model,
        temperature=0.0,
        max_tokens=16,
        use_cache=False,
        budget_subject=SYNTHETIC_SUBJECT,
        budget_clinic_id=SYNTHETIC_CLINIC_ID,
    )
    result["quota_check"] = {
        "status": "PASS_429" if isinstance(quota_response, LLMUnavailable) and "Quota IA dépassée" in quota_response.reason else "FAIL",
        "response_type": type(quota_response).__name__,
        "detail": getattr(quota_response, "reason", ""),
    }
    if quota_client is not client:
        await quota_client.aclose()

    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result["status"] != "PROVIDER_PASS" or result["quota_check"]["status"] != "PASS_429":
        raise SystemExit(1)


if __name__ == "__main__":
    asyncio.run(main())
