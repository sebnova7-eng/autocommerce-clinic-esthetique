from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone

from config import get_settings
from core.llm_budget import LLMBudgetExceeded, reserve_budget


async def main() -> None:
    settings = get_settings().model_copy(update={
        "env": "production",
        "llm_max_requests_per_user_day": 100,
        "llm_daily_token_budget": 100_000,
        "llm_monthly_token_budget": 1_000_000,
        "llm_max_requests_per_clinic_day": 1_000,
    })
    try:
        await reserve_budget(
            settings,
            "clinic:1:redis-fail-closed-probe:user-1",
            10,
            clinic_id=1,
        )
    except LLMBudgetExceeded as exc:
        print(json.dumps({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "status": "FAIL_CLOSED_PASS",
            "detail": str(exc),
        }, ensure_ascii=False))
        return
    print(json.dumps({
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "status": "FAIL_CLOSED_FAIL",
        "detail": "reserve_budget returned without Redis",
    }, ensure_ascii=False))
    raise SystemExit(1)


if __name__ == "__main__":
    asyncio.run(main())
