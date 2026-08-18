from __future__ import annotations

import asyncio
import json
import multiprocessing as mp
import os
import time
from datetime import datetime, timezone
from typing import Any

from redis.asyncio import from_url

from config import get_settings
from core.llm_budget import LLMBudgetExceeded, reserve_budget


QUOTA = 1
MAX_TOKENS = 10
CLINICS = (1, 2)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def make_settings() -> Any:
    settings = get_settings()
    return settings.model_copy(update={
        "env": "production",
        "llm_max_requests_per_user_day": 100,
        "llm_daily_token_budget": 100_000,
        "llm_monthly_token_budget": 1_000_000,
        "llm_max_requests_per_clinic_day": QUOTA,
    })


async def clear_campaign_keys(redis_url: str) -> None:
    client = from_url(redis_url, decode_responses=True)
    keys: list[str] = []
    async for key in client.scan_iter(match="llm:*"):
        keys.append(key)
    if keys:
        await client.delete(*keys)
    await client.aclose()


async def read_campaign_keys(redis_url: str) -> dict[str, int]:
    client = from_url(redis_url, decode_responses=True)
    result: dict[str, int] = {}
    async for key in client.scan_iter(match="llm:req:clinic_*"):
        result[key] = int(await client.get(key) or 0)
    await client.aclose()
    return result


async def reserve_one(worker: str, clinic_id: int, phase: str) -> dict[str, Any]:
    settings = make_settings()
    subject = f"clinic:{clinic_id}:redis-campaign:{phase}:{worker}"
    started = time.perf_counter()
    try:
        await reserve_budget(
            settings,
            subject,
            MAX_TOKENS,
            clinic_id=clinic_id,
        )
        return {
            "worker": worker,
            "clinic_id": clinic_id,
            "phase": phase,
            "status": "PASS",
            "elapsed_ms": round((time.perf_counter() - started) * 1000, 2),
            "timestamp": utc_now(),
        }
    except LLMBudgetExceeded as exc:
        return {
            "worker": worker,
            "clinic_id": clinic_id,
            "phase": phase,
            "status": "429",
            "detail": str(exc),
            "elapsed_ms": round((time.perf_counter() - started) * 1000, 2),
            "timestamp": utc_now(),
        }
    except Exception as exc:  # pragma: no cover - staging diagnostic
        return {
            "worker": worker,
            "clinic_id": clinic_id,
            "phase": phase,
            "status": "ERROR",
            "detail": f"{type(exc).__name__}: {exc}",
            "elapsed_ms": round((time.perf_counter() - started) * 1000, 2),
            "timestamp": utc_now(),
        }


def worker_main(worker: str, barrier: mp.Barrier, output: mp.Queue) -> None:
    async def run() -> None:
        barrier.wait()
        results = await asyncio.gather(
            *(reserve_one(worker, clinic_id, "shared-quota") for clinic_id in CLINICS)
        )
        for result in results:
            output.put(result)

    asyncio.run(run())


async def run_campaign() -> dict[str, Any]:
    settings = make_settings()
    redis_url = settings.redis_url
    await clear_campaign_keys(redis_url)

    context = mp.get_context("spawn")
    barrier = context.Barrier(2)
    output = context.Queue()
    processes = [
        context.Process(target=worker_main, args=(f"worker-{index}", barrier, output))
        for index in (1, 2)
    ]
    started = utc_now()
    for process in processes:
        process.start()
    for process in processes:
        process.join(30)
    results = [output.get(timeout=5) for _ in range(4)]
    exit_codes = {process.name: process.exitcode for process in processes}
    keys = await read_campaign_keys(redis_url)

    by_clinic: dict[str, dict[str, int]] = {}
    for clinic_id in CLINICS:
        clinic_results = [item for item in results if item["clinic_id"] == clinic_id]
        by_clinic[str(clinic_id)] = {
            "pass": sum(item["status"] == "PASS" for item in clinic_results),
            "429": sum(item["status"] == "429" for item in clinic_results),
            "error": sum(item["status"] == "ERROR" for item in clinic_results),
        }

    outcome = {
        "campaign": "redis_shared_multi_process",
        "started_at": started,
        "redis_url_host": redis_url.split("@")[-1].split("/")[0] if redis_url else "",
        "process_count": len(processes),
        "quota_clinic_requests": QUOTA,
        "clinics": list(CLINICS),
        "results": sorted(results, key=lambda item: (item["clinic_id"], item["worker"])),
        "by_clinic": by_clinic,
        "redis_clinic_request_keys": keys,
        "process_exit_codes": exit_codes,
        "assertions": {
            "two_processes_clean_exit": all(code == 0 for code in exit_codes.values()),
            "one_pass_per_clinic": all(value["pass"] == 1 for value in by_clinic.values()),
            "one_429_per_clinic": all(value["429"] == 1 for value in by_clinic.values()),
            "no_process_errors": all(value["error"] == 0 for value in by_clinic.values()),
        },
    }
    return outcome


if __name__ == "__main__":
    print(json.dumps(asyncio.run(run_campaign()), ensure_ascii=False, indent=2))
