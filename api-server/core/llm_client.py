"""
AutoCommerce Clinic — Wrapper LLM unifié (production-grade).

But : remplacer N stubs par **un seul** client async qui parle à plusieurs
providers et garantit :

- Retry exponentiel (1s, 2s, 4s, 8s) avec jitter ;
- Timeout strict ;
- Streaming (callback coroutine) ;
- Mode dégradé **honnête** : si aucune clé n'est configurée, ``chat()``
  renvoie un objet structuré ``LLMUnavailable`` (NE renvoie PAS de faux texte) ;
- Idempotence par ``cache_key`` court (5 min) ;
- Audit logging (info-level WARNING sur rate-limit) ;
- Zéro SDK propriétaire (httpx.AsyncClient brut) — pas d'ajout de dépendance.

Providers supportés :
- OpenAI (Chat Completions)
- OpenRouter (mêmes appels, base URL différente)
- Anthropic Messages API
- Gemini generateContent
- Mistral Chat

Sélection via ``settings.llm_provider`` ("openai" par défaut).
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import random
import re
import time
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Dict, List, Optional, Union

import httpx

from core.llm_budget import LLMBudgetExceeded, reserve_budget

logger = logging.getLogger("llm_client")


# ─── Modèles de retour ────────────────────────────────────────────────


@dataclass
class LLMUnavailable:
    """Marqueur honnête : aucun LLM n'a été appelé. ``.reason`` explique pourquoi."""

    provider: str
    reason: str

    @property
    def is_unavailable(self) -> bool:  # pragma: no cover - trivial
        return True


@dataclass
class LLMResponse:
    text: str
    provider: str
    model: str
    usage: Dict[str, int] = field(default_factory=dict)
    latency_ms: int = 0
    cached: bool = False


# ─── Cache court (anti-burst Ctrl+F5 utilisateur) ──────────────────────

_CACHE: Dict[str, LLMResponse] = {}
_CACHE_TS: Dict[str, float] = {}
_CACHE_TTL_SECONDS = 300  # 5 min


def _cache_get(key: str) -> Optional[LLMResponse]:
    ts = _CACHE_TS.get(key)
    if ts is None:
        return None
    if time.time() - ts > _CACHE_TTL_SECONDS:
        _CACHE.pop(key, None)
        _CACHE_TS.pop(key, None)
        return None
    r = _CACHE.get(key)
    if r:
        r.cached = True
    return r


def _cache_set(key: str, response: LLMResponse) -> None:
    _CACHE[key] = response
    _CACHE_TS[key] = time.time()


def cache_clear() -> None:
    _CACHE.clear()
    _CACHE_TS.clear()


def make_cache_key(messages: List[Dict[str, str]], **kwargs: Any) -> str:
    h = hashlib.sha256()
    h.update(json.dumps(messages, sort_keys=True, ensure_ascii=False).encode())
    h.update(json.dumps(kwargs, sort_keys=True, default=str).encode())
    return h.hexdigest()


def pseudonymize_pii(data: Any) -> Any:
    """
    Parcourt récursivement un objet (dict, list, str) et masque les PII
    (noms, téléphones, emails) pour les prompts LLM.
    """
    if isinstance(data, dict):
        new_dict = {}
        for k, v in data.items():
            # Masquage par clé
            if k in ("nom", "name", "full_name", "patient_name"):
                if isinstance(v, str) and v:
                    parts = v.split(" ")
                    if len(parts) > 1:
                        new_dict[k] = f"{parts[0]} {parts[-1][:1]}***"
                    else:
                        new_dict[k] = f"{v[:1]}***"
                else:
                    new_dict[k] = "Anonyme"
            elif k in ("email", "courriel"):
                new_dict[k] = "patient@email-masque.com" if v else None
            elif k in ("telephone", "phone", "tel"):
                if v:
                    s = str(v)
                    new_dict[k] = f"{s[:4]}******"
                else:
                    new_dict[k] = None
            elif k in ("notes", "compte_rendu", "description"):
                if isinstance(v, str):
                    # Nettoyage regex des emails et numéros dans le texte libre
                    v = re.sub(r"[\w\.-]+@[\w\.-]+", "[EMAIL]", v)
                    v = re.sub(r"\d{8,}", "[TEL]", v)
                    new_dict[k] = v
                else:
                    new_dict[k] = v
            else:
                new_dict[k] = pseudonymize_pii(v)
        return new_dict
    elif isinstance(data, list):
        return [pseudonymize_pii(i) for i in data]
    return data


# ─── Client ────────────────────────────────────────────────────────────

DEFAULT_TIMEOUT_S = 30.0
RETRY_BACKOFF_S = (1.0, 2.0, 4.0, 8.0)


class LLMClient:
    """Singleton async — un seul ``httpx.AsyncClient`` réutilisé."""

    def __init__(self, settings: Any) -> None:
        self._settings = settings
        self._client: Optional[httpx.AsyncClient] = None

    async def _http(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=DEFAULT_TIMEOUT_S,
                headers={"Content-Type": "application/json"},
            )
        return self._client

    async def aclose(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    # ── Dispatch par provider ──────────────────────────────────────

    async def chat(
        self,
        messages: List[Dict[str, str]],
        *,
        model: Optional[str] = None,
        temperature: float = 0.2,
        max_tokens: int = 1024,
        stream: bool = False,
        on_token: Optional[Callable[[str], Awaitable[None]]] = None,
        use_cache: bool = True,
        provider_override: Optional[str] = None,
        response_format_json: bool = False,
        budget_subject: Optional[str] = None,
        budget_clinic_id: Optional[int] = None,
    ) -> Union[LLMResponse, LLMUnavailable]:
        # Gate IA : vérification globale
        if not getattr(self._settings, "llm_enabled", True):
            return LLMUnavailable("global", "services IA désactivés par l'administrateur")

        provider = (
            provider_override
            or getattr(self._settings, "llm_provider", "openai")
            or "openai"
        ).lower()
        allowed_providers = {
            item.strip().lower()
            for item in str(getattr(self._settings, "llm_provider_allowlist", provider)).split(",")
            if item.strip()
        }
        if provider not in allowed_providers:
            return LLMUnavailable(provider, "provider refusé par l'allowlist de production")
        max_tokens = min(
            int(max_tokens),
            int(getattr(self._settings, "llm_max_tokens_per_request", max_tokens)),
        )
        try:
            await reserve_budget(
                self._settings,
                budget_subject or "global",
                max_tokens,
                clinic_id=budget_clinic_id,
            )
        except LLMBudgetExceeded as exc:
            logger.warning(
                "llm_budget_exceeded clinic_id=%s subject=%s provider=%s",
                budget_clinic_id,
                budget_subject,
                provider,
            )
            return LLMUnavailable(provider, str(exc))

        # Garde-fou : refus de démarrer en prod sans clé LLM
        key_check = self._require_key(provider)
        if isinstance(key_check, LLMUnavailable):
            return key_check

        cache_key = make_cache_key(messages, model=model, temperature=temperature,
                                   max_tokens=max_tokens, provider=provider,
                                   response_format_json=response_format_json)
        if use_cache:
            cached = _cache_get(cache_key)
            if cached is not None:
                logger.info("llm_cache_hit provider=%s len=%d", provider, len(cached.text))
                return cached

        # Retry loop
        last_exc: Optional[Exception] = None
        for attempt, delay in enumerate(RETRY_BACKOFF_S, start=1):
            try:
                t0 = time.perf_counter()
                if provider == "openai":
                    text, usage = await self._call_openai(
                        messages, model or self._settings.openai_model,
                        temperature, max_tokens, stream, on_token,
                        response_format_json,
                    )
                elif provider == "openrouter":
                    text, usage = await self._call_openrouter(
                        messages, model or self._settings.openai_model,
                        temperature, max_tokens, response_format_json,
                    )
                elif provider == "anthropic":
                    text, usage = await self._call_anthropic(
                        messages, model or getattr(self._settings, "anthropic_model", "claude-3-5-sonnet-latest"),
                        temperature, max_tokens, response_format_json,
                    )
                elif provider == "gemini":
                    text, usage = await self._call_gemini(
                        messages, model or getattr(self._settings, "gemini_model", "gemini-1.5-flash"),
                        temperature, max_tokens, response_format_json,
                    )
                elif provider == "mistral":
                    text, usage = await self._call_mistral(
                        messages, model or getattr(self._settings, "mistral_model", "mistral-large-latest"),
                        temperature, max_tokens, response_format_json,
                    )
                else:
                    return LLMUnavailable(provider, f"provider inconnu: {provider!r}")
                latency_ms = int((time.perf_counter() - t0) * 1000)
                resp = LLMResponse(text=text, provider=provider,
                                   model=model or "", usage=usage, latency_ms=latency_ms)
                if use_cache:
                    _cache_set(cache_key, resp)
                return resp
            except httpx.HTTPStatusError as exc:
                last_exc = exc
                if exc.response.status_code in (429, 500, 502, 503, 504):
                    logger.warning("llm_retry provider=%s attempt=%d status=%s",
                                   provider, attempt, exc.response.status_code)
                    await asyncio.sleep(delay + random.random() * 0.4)
                    continue
                # 4xx autre : pas de retry
                logger.error("llm_4xx provider=%s status=%s body=%s",
                             provider, exc.response.status_code, exc.response.text[:200])
                return LLMUnavailable(
                    provider, f"HTTP {exc.response.status_code} : {exc.response.text[:120]}"
                )
            except (httpx.TimeoutException, httpx.ConnectError) as exc:
                last_exc = exc
                logger.warning("llm_timeout provider=%s attempt=%d", provider, attempt)
                await asyncio.sleep(delay + random.random() * 0.4)

        return LLMUnavailable(
            provider, f"échec après {len(RETRY_BACKOFF_S)} tentatives : {last_exc}"
        )

    # ── Appels HTTP sortants par provider ──────────────────────────

    async def _call_openai(
        self, messages, model, temperature, max_tokens, stream, on_token,
        response_format_json,
    ):
        url = "https://api.openai.com/v1/chat/completions"
        api_key = self._api_key("openai")
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if response_format_json:
            payload["response_format"] = {"type": "json_object"}
        if stream:
            return await self._stream_openai(url, api_key, payload, on_token)
        http = await self._http()
        r = await http.post(url, headers={"Authorization": f"Bearer {api_key}"},
                             json=payload)
        r.raise_for_status()
        data = r.json()
        text = data["choices"][0]["message"]["content"] or ""
        usage = data.get("usage", {})
        return text, usage

    async def _stream_openai(self, url, api_key, payload, on_token):
        http = await self._http()
        async with http.stream("POST", url,
                               headers={"Authorization": f"Bearer {api_key}"},
                               json=payload) as r:
            r.raise_for_status()
            collected: List[str] = []
            async for line in r.aiter_lines():
                if not line.startswith("data: "):
                    continue
                chunk = line[len("data: "):].strip()
                if chunk == "[DONE]":
                    break
                try:
                    obj = json.loads(chunk)
                except json.JSONDecodeError:
                    continue
                delta = (
                    obj.get("choices", [{}])[0].get("delta", {}).get("content")
                )
                if delta:
                    collected.append(delta)
                    if on_token is not None:
                        await on_token(delta)
            return "".join(collected), {}

    async def _call_openrouter(self, messages, model, temperature, max_tokens, response_format_json):
        url = "https://openrouter.ai/api/v1/chat/completions"
        api_key = getattr(self._settings, "openrouter_api_key", "")
        if not api_key:
            raise httpx.HTTPStatusError(
                "no openrouter api key", request=None, response=None
            )
        payload = {
            "model": model, "messages": messages,
            "temperature": temperature, "max_tokens": max_tokens,
        }
        if response_format_json:
            payload["response_format"] = {"type": "json_object"}
        http = await self._http()
        r = await http.post(url, headers={"Authorization": f"Bearer {api_key}"}, json=payload)
        r.raise_for_status()
        data = r.json()
        return data["choices"][0]["message"]["content"] or "", data.get("usage", {})

    async def _call_anthropic(self, messages, model, temperature, max_tokens, response_format_json):
        url = "https://api.anthropic.com/v1/messages"
        api_key = getattr(self._settings, "anthropic_api_key", "")
        if not api_key:
            raise httpx.HTTPStatusError("no anthropic api key", request=None, response=None)
        system = "\n\n".join(m["content"] for m in messages if m.get("role") == "system")
        convo = [{"role": m["role"], "content": m["content"]}
                 for m in messages if m.get("role") in ("user", "assistant")]
        payload = {
            "model": model, "max_tokens": max_tokens,
            "temperature": temperature, "system": system, "messages": convo,
        }
        http = await self._http()
        r = await http.post(
            url,
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
            },
            json=payload,
        )
        r.raise_for_status()
        data = r.json()
        text = "".join(b.get("text", "") for b in data.get("content", []))
        usage = data.get("usage", {})
        return text, usage

    async def _call_gemini(self, messages, model, temperature, max_tokens, response_format_json):
        api_key = getattr(self._settings, "gemini_api_key", "")
        if not api_key:
            raise httpx.HTTPStatusError("no gemini api key", request=None, response=None)
        sys_parts: List[Dict[str, Any]] = []
        convo_parts: List[Dict[str, Any]] = []
        for m in messages:
            if m.get("role") == "system":
                sys_parts.append({"text": m["content"]})
            else:
                role = "user" if m["role"] == "user" else "model"
                convo_parts.append({"role": role, "parts": [{"text": m["content"]}]})
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        payload: Dict[str, Any] = {
            "contents": convo_parts,
            "generationConfig": {"temperature": temperature, "maxOutputTokens": max_tokens},
        }
        if sys_parts:
            payload["systemInstruction"] = {"parts": sys_parts}
        if response_format_json:
            payload["generationConfig"]["responseMimeType"] = "application/json"
        http = await self._http()
        r = await http.post(url, params={"key": api_key}, json=payload)
        r.raise_for_status()
        data = r.json()
        try:
            text = data["candidates"][0]["content"]["parts"][0]["text"]
        except (KeyError, IndexError):
            text = ""
        usage = data.get("usageMetadata", {})
        return text, usage

    async def _call_mistral(self, messages, model, temperature, max_tokens, response_format_json):
        url = "https://api.mistral.ai/v1/chat/completions"
        api_key = getattr(self._settings, "mistral_api_key", "")
        if not api_key:
            raise httpx.HTTPStatusError("no mistral api key", request=None, response=None)
        payload = {
            "model": model, "messages": messages,
            "temperature": temperature, "max_tokens": max_tokens,
        }
        if response_format_json:
            payload["response_format"] = {"type": "json_object"}
        http = await self._http()
        r = await http.post(url, headers={"Authorization": f"Bearer {api_key}"}, json=payload)
        r.raise_for_status()
        data = r.json()
        text = data["choices"][0]["message"]["content"] or ""
        return text, data.get("usage", {})

    # ── Garde clé ─────────────────────────────────────────────────

    def _api_key(self, provider: str) -> str:
        """Return the normalized provider key from settings or environment."""
        attr = {
            "openai": "openai_api_key",
            "openrouter": "openrouter_api_key",
            "anthropic": "anthropic_api_key",
            "gemini": "gemini_api_key",
            "mistral": "mistral_api_key",
        }.get(provider)
        env_name = {
            "openai": "OPENAI_API_KEY",
            "openrouter": "OPENROUTER_API_KEY",
            "anthropic": "ANTHROPIC_API_KEY",
            "gemini": "GEMINI_API_KEY",
            "mistral": "MISTRAL_API_KEY",
        }.get(provider)
        if attr and hasattr(self._settings, attr):
            # Settings is the source of truth; an explicit empty value must
            # remain unavailable instead of silently inheriting CI secrets.
            return str(getattr(self._settings, attr, "") or "").strip()
        return str(os.environ.get(env_name, "") if env_name else "").strip()

    def _require_key(self, provider: str):
        required_attr = {
            "openai": "openai_api_key",
            "openrouter": "openrouter_api_key",
            "anthropic": "anthropic_api_key",
            "gemini": "gemini_api_key",
            "mistral": "mistral_api_key",
        }.get(provider)
        if required_attr is None:
            return LLMUnavailable(provider, f"provider non configuré: {provider!r}")
        val = self._api_key(provider)
        if not val:
            return LLMUnavailable(
                provider,
                f"aucune clé pour {provider!r} ; renseignez settings.{required_attr}",
            )
        return None  # OK


# ── Factory singleton ─────────────────────────────────────────────────

_client_singleton: Optional[LLMClient] = None


def get_llm_client(settings: Any) -> LLMClient:
    """Singleton-safe ; ne réouvre jamais le pool httpx en prod."""
    global _client_singleton
    if _client_singleton is None:
        _client_singleton = LLMClient(settings)
    return _client_singleton


async def reset_llm_client() -> None:
    global _client_singleton
    if _client_singleton is not None:
        await _client_singleton.aclose()
    _client_singleton = None
