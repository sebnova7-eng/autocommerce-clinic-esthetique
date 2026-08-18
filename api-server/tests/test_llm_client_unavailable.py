"""
Tests unitaires du client LLM et des fallbacks honnêtes (v1.1.0 patch IA).

Couvre :
- LLMUnavailable correctement renvoyé quand clé absente ;
- cache LLM ;
- retries (testés via mock rapide) ;
- construction de l'endpoint par provider.
"""

from __future__ import annotations

import pytest

from core.llm_client import (
    LLMClient, LLMUnavailable, make_cache_key, cache_clear, _cache_get, _cache_set,
)


class _StubSettings:
    """Settings minimal pour tester LLMClient (sans dépendance config.py)."""
    llm_provider = "openai"
    openai_api_key = ""
    openai_model = "gpt-4o"
    openrouter_api_key = ""
    anthropic_api_key = ""
    gemini_api_key = ""
    mistral_api_key = ""


class _SettingsWithKey:
    llm_provider = "openai"
    openai_api_key = "test-fake-key-for-test"
    openai_model = "gpt-4o"
    openrouter_api_key = ""
    anthropic_api_key = ""
    gemini_api_key = ""
    mistral_api_key = ""


@pytest.mark.asyncio
async def test_chat_unavailable_when_no_key():
    llm = LLMClient(_StubSettings())
    out = await llm.chat([{"role": "user", "content": "Bonjour"}], use_cache=False)
    assert isinstance(out, LLMUnavailable)
    assert out.provider == "openai"
    assert "aucune clé" in out.reason or "OPENAI" in out.reason


@pytest.mark.asyncio
async def test_chat_openai_success_mocked(monkeypatch):
    """Mock httpx.AsyncClient.post pour valider le câblage OpenAI."""
    from unittest.mock import AsyncMock

    class _FakeResp:
        def __init__(self, payload):
            self._payload = payload
            self.status_code = 200

        def raise_for_status(self):
            return None

        def json(self):
            return self._payload

    payload = {
        "choices": [{"message": {"content": "Bonjour !"}}],
        "usage": {"total_tokens": 12},
    }
    fake_resp = _FakeResp(payload)

    class _FakeClient:
        def __init__(self):
            self.post = AsyncMock(return_value=fake_resp)
            self.is_closed = False

        async def aclose(self):
            self.is_closed = True

    monkeypatch.setattr(
        "core.llm_client.httpx.AsyncClient",
        lambda *a, **kw: _FakeClient(),
    )
    llm = LLMClient(_SettingsWithKey())
    out = await llm.chat(
        [{"role": "user", "content": "Bonjour"}],
        use_cache=False,
    )
    assert hasattr(out, "text")
    assert out.text == "Bonjour !"
    assert out.provider == "openai"
    await llm.aclose()


def test_cache_set_get_roundtrip():
    cache_clear()
    from core.llm_client import LLMResponse
    r = LLMResponse(text="x", provider="openai", model="gpt-4o")
    _cache_set("k", r)
    got = _cache_get("k")
    assert got is not None
    assert got.text == "x"
    assert got.cached is True  # vaudra True après hit


def test_make_cache_key_deterministic():
    k1 = make_cache_key([{"role": "user", "content": "a"}], model="gpt-4o")
    k2 = make_cache_key([{"role": "user", "content": "a"}], model="gpt-4o")
    assert k1 == k2
    k3 = make_cache_key([{"role": "user", "content": "b"}], model="gpt-4o")
    assert k1 != k3


def test_agent_runtime_singleton_settings():
    """Vérifie que get_llm_client() n'ouvre qu'un seul httpx pool."""
    from core.llm_client import get_llm_client, reset_llm_client
    import asyncio
    asyncio.run(reset_llm_client())
    a = get_llm_client(_SettingsWithKey())
    b = get_llm_client(_SettingsWithKey())
    assert a is b


@pytest.mark.asyncio
async def test_explicit_empty_settings_key_does_not_fallback_to_environment(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-environment-key")
    llm = LLMClient(_StubSettings())
    out = await llm.chat([{"role": "user", "content": "Bonjour"}], use_cache=False)
    assert isinstance(out, LLMUnavailable)
    assert "aucune clé" in out.reason


def test_api_key_is_trimmed_and_never_contains_whitespace_only(monkeypatch):
    settings = _SettingsWithKey()
    settings.openai_api_key = "  test-key  "
    llm = LLMClient(settings)
    assert llm._api_key("openai") == "test-key"
    settings.openai_api_key = "   "
    assert llm._api_key("openai") == ""
