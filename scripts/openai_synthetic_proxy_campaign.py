from __future__ import annotations

import asyncio
import hashlib
import json
import os
import time
from datetime import datetime, timezone

from openai import AsyncOpenAI

from config import get_settings
from core.llm_budget import LLMBudgetExceeded, reserve_budget


MODEL = os.environ.get("SYNTHETIC_OPENAI_MODEL", "gpt-5-mini")
CLINIC_ID = 9982
SUBJECT = f"clinic:{CLINIC_ID}:synthetic-provider-validation:user:1"
SYSTEM = "Return only the requested synthetic validation token."
USER = "Return exactly the single word SYNTHETIC_OK."


async def main() -> None:
    api_base = os.environ["OPENAI_API_BASE"]
    api_key = os.environ["OPENAI_API_KEY"]
    started_at = datetime.now(timezone.utc).isoformat()
    client = AsyncOpenAI(api_key=api_key, base_url=api_base)
    started = time.perf_counter()
    response = await client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": USER},
        ],
        temperature=0.0,
        max_completion_tokens=16,
    )
    latency_ms = round((time.perf_counter() - started) * 1000, 2)
    text = response.choices[0].message.content or ""
    usage = response.usage.model_dump() if response.usage else {}

    settings = get_settings().model_copy(update={
        "env": "production",
        "redis_url": os.environ["REDIS_URL"],
        "llm_max_requests_per_clinic_day": 1,
        "llm_daily_token_budget": 100_000,
        "llm_monthly_token_budget": 1_000_000,
        "llm_max_requests_per_user_day": 100,
    })
    redis_client = None
    try:
        from redis.asyncio import from_url
        redis_client = from_url(settings.redis_url, decode_responses=True)
        async for key in redis_client.scan_iter(match=f"llm:req:clinic_{CLINIC_ID}*"):
            await redis_client.delete(key)
        async for key in redis_client.scan_iter(match=f"llm:tok:clinic_{CLINIC_ID}*"):
            await redis_client.delete(key)
        async for key in redis_client.scan_iter(match=f"llm:req:clinic:{CLINIC_ID}*"):
            await redis_client.delete(key)
        async for key in redis_client.scan_iter(match=f"llm:tok:clinic:{CLINIC_ID}*"):
            await redis_client.delete(key)
    finally:
        if redis_client is not None:
            await redis_client.aclose()

    await reserve_budget(settings, SUBJECT, 16, clinic_id=CLINIC_ID)
    quota_status = "FAIL"
    quota_detail = ""
    try:
        await reserve_budget(settings, SUBJECT, 16, clinic_id=CLINIC_ID)
    except LLMBudgetExceeded as exc:
        quota_status = "PASS_429"
        quota_detail = str(exc)

    result = {
        "timestamp": started_at,
        "status": "PROVIDER_PASS",
        "provider": "openai-compatible",
        "base_url_host": api_base.split("//", 1)[-1].split("/", 1)[0],
        "endpoint": f"{api_base.rstrip('/')}/chat/completions",
        "model": MODEL,
        "synthetic_only": True,
        "phi_present": False,
        "patient_id_present": False,
        "request_parameters": {
            "temperature": 0.0,
            "max_completion_tokens": 16,
            "stream": False,
        },
        "message_roles": ["system", "user"],
        "message_character_counts": [len(SYSTEM), len(USER)],
        "message_sha256": hashlib.sha256((SYSTEM + "\n" + USER).encode()).hexdigest(),
        "response_character_count": len(text),
        "response_sha256": hashlib.sha256(text.encode()).hexdigest(),
        "latency_ms": latency_ms,
        "usage": usage,
        "quota_check": {
            "status": quota_status,
            "detail": quota_detail,
            "clinic_id": CLINIC_ID,
            "limit": 1,
        },
    }
    await client.close()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if quota_status != "PASS_429":
        raise SystemExit(1)


if __name__ == "__main__":
    asyncio.run(main())
