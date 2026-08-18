"""Quotas et garde-fous de consommation LLM.

Le compteur est stocké dans Redis quand il est disponible afin de rester
partagé entre API, worker et beat. Le fallback mémoire est réservé aux tests
et au développement; il applique les mêmes dimensions de quota.
"""

from __future__ import annotations

import asyncio
import re
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import HTTPException, status


class LLMBudgetExceeded(RuntimeError):
    """Le budget de requêtes ou de tokens réservé est dépassé."""


_memory_lock = asyncio.Lock()
_memory_requests: dict[str, int] = defaultdict(int)
_memory_tokens: dict[str, int] = defaultdict(int)
_memory_monthly_tokens: dict[str, int] = defaultdict(int)
_memory_clinic_requests: dict[str, int] = defaultdict(int)


def clear_memory_budgets() -> None:
    """Réinitialise les compteurs mémoire pour les tests isolés."""
    _memory_requests.clear()
    _memory_tokens.clear()
    _memory_monthly_tokens.clear()
    _memory_clinic_requests.clear()


def _day_key() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _month_key() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m")


def _subject_key(subject: str | None) -> str:
    safe = (subject or "global").replace(":", "_")[:100]
    return f"{safe}:{_day_key()}"


def _clinic_from_subject(subject: str | None) -> Optional[int]:
    """Extrait uniquement un clinic_id déjà scoppé côté serveur.

    Les sujets générés par les routes ont la forme ``clinic:<id>:...``. Une
    valeur fournie dans le texte utilisateur ne passe jamais par cette
    fonction; le sujet est construit par le backend.
    """
    match = re.match(r"^clinic:(\d+)(?::|$)", subject or "")
    if not match:
        return None
    clinic_id = int(match.group(1))
    return clinic_id if clinic_id > 0 else None


def _resolve_budget_clinic_id(
    settings: Any,
    subject: str | None,
    clinic_id: Optional[int],
) -> Optional[int]:
    """Résout le tenant sans accepter un identifiant venant du frontend."""
    if clinic_id is not None:
        if int(clinic_id) <= 0:
            raise LLMBudgetExceeded("Contexte clinique invalide")
        return int(clinic_id)

    subject_clinic_id = _clinic_from_subject(subject)
    if subject_clinic_id is not None:
        return subject_clinic_id

    # Le contexte ContextVar est posé par l’authentification backend.
    try:
        from middleware.clinic_context import get_current_clinic_id
        return get_current_clinic_id()
    except (ImportError, RuntimeError):
        pass

    configured_clinic_id = getattr(settings, "clinic_id", None)
    env = str(getattr(settings, "env", "development")).lower()
    if env in {"test", "development"} and configured_clinic_id:
        return int(configured_clinic_id)
    if env == "production" and getattr(settings, "is_internal_single_clinic", False) and configured_clinic_id:
        return int(configured_clinic_id)
    if env == "production":
        raise LLMBudgetExceeded("Contexte clinique absent : appel IA refusé en production")
    return None


async def reserve_budget(
    settings: Any,
    subject: str | None,
    max_tokens: int,
    clinic_id: Optional[int] = None,
) -> None:
    """Réserve une enveloppe avant l’appel provider.

    La réservation conservatrice par ``max_tokens`` évite qu’un burst dépasse
    le budget avant que les réponses fournisseurs soient connues. Le quota
    clinique est toujours calculé avec le tenant authentifié, jamais avec un
    ``clinic_id`` fourni dans la payload utilisateur.
    """
    max_tokens = max(1, int(max_tokens))
    resolved_clinic_id = _resolve_budget_clinic_id(settings, subject, clinic_id)
    subject_key = _subject_key(subject)
    month_subject_key = f"{(subject or 'global').replace(':', '_')[:100]}:{_month_key()}"
    clinic_key = _subject_key(
        f"clinic:{resolved_clinic_id}" if resolved_clinic_id is not None else "global"
    )
    request_limit = int(getattr(settings, "llm_max_requests_per_user_day", 100))
    token_limit = int(getattr(settings, "llm_daily_token_budget", 100_000))
    monthly_token_limit = int(getattr(settings, "llm_monthly_token_budget", 1_000_000))
    clinic_request_limit = int(getattr(settings, "llm_max_requests_per_clinic_day", 1_000))

    client = None
    try:
        from redis.asyncio import from_url
        redis_url = getattr(settings, "redis_url", "")
        if redis_url:
            client = from_url(redis_url, decode_responses=True)
            req_key = f"llm:req:{subject_key}"
            tok_key = f"llm:tok:{subject_key}"
            month_tok_key = f"llm:tok:{month_subject_key}"
            clinic_req_key = f"llm:req:{clinic_key}"
            pipe = client.pipeline()
            pipe.incr(req_key)
            pipe.incrby(tok_key, max_tokens)
            pipe.incrby(month_tok_key, max_tokens)
            pipe.incr(clinic_req_key)
            pipe.expire(req_key, 172800)
            pipe.expire(tok_key, 172800)
            pipe.expire(month_tok_key, 32 * 86400)
            pipe.expire(clinic_req_key, 172800)
            req_count, token_count, month_token_count, clinic_req_count, *_ = await pipe.execute()
            if (
                req_count > request_limit
                or token_count > token_limit
                or month_token_count > monthly_token_limit
                or clinic_req_count > clinic_request_limit
            ):
                rollback = client.pipeline()
                rollback.decr(req_key)
                rollback.decrby(tok_key, max_tokens)
                rollback.decrby(month_tok_key, max_tokens)
                rollback.decr(clinic_req_key)
                await rollback.execute()
                raise LLMBudgetExceeded("Quota IA dépassée")
            return
    except LLMBudgetExceeded:
        raise
    except Exception:
        # Redis indisponible : en production, refuser pour éviter une
        # consommation sans compteur central; en test/dev, fallback borné.
        if str(getattr(settings, "env", "")).lower() == "production":
            raise LLMBudgetExceeded("Compteur IA indisponible : appel refusé en production")
    finally:
        if client is not None:
            try:
                await client.aclose()
            except Exception:
                pass

    async with _memory_lock:
        _memory_requests[subject_key] += 1
        _memory_tokens[subject_key] += max_tokens
        _memory_monthly_tokens[month_subject_key] += max_tokens
        _memory_clinic_requests[clinic_key] += 1
        if (
            _memory_requests[subject_key] > request_limit
            or _memory_tokens[subject_key] > token_limit
            or _memory_monthly_tokens[month_subject_key] > monthly_token_limit
            or _memory_clinic_requests[clinic_key] > clinic_request_limit
        ):
            _memory_requests[subject_key] -= 1
            _memory_tokens[subject_key] -= max_tokens
            _memory_monthly_tokens[month_subject_key] -= max_tokens
            _memory_clinic_requests[clinic_key] -= 1
            raise LLMBudgetExceeded("Quota IA dépassée")


def budget_http_exception(exc: LLMBudgetExceeded) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail=str(exc),
        headers={"Retry-After": "3600"},
    )
