"""Tests — Bloc 1 : Webhook Omnicanal multi-canal"""

import hashlib
import hmac
import json

import pytest
from fastapi.testclient import TestClient

from main import app
from api.deps import get_db
from config import get_settings


@pytest.fixture
def client(db):
    async def _override_get_db():
        yield db

    app.dependency_overrides[get_db] = _override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


def _sign(secret: str, body: bytes) -> str:
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def test_webhook_rejects_when_secret_not_configured(client, monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "social_webhook_secret", "")
    r = client.post("/api/v1/omnicanal/webhook/whatsapp",
                     json={"test": True})
    assert r.status_code == 503


def test_webhook_rejects_missing_signature(client, monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "social_webhook_secret", "un-secret-partage")

    body = json.dumps({
        "object": "whatsapp_business_account",
        "entry": [{
            "changes": [{
                "value": {
                    "messages": [{"from": "+21600000099", "type": "text", "text": {"body": "test"}}],
                    "contacts": []
                }
            }]
        }]
    }).encode()

    r = client.post("/api/v1/omnicanal/webhook/whatsapp",
                     content=body,
                     headers={"Content-Type": "application/json"})
    assert r.status_code == 401


def test_webhook_accepts_valid_signature(client, monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "social_webhook_secret", "un-secret-partage")

    body = json.dumps({
        "object": "whatsapp_business_account",
        "entry": [{
            "changes": [{
                "value": {
                    "messages": [{"from": "+21600000099", "type": "text", "text": {"body": "test"}}],
                    "contacts": []
                }
            }]
        }]
    }).encode()
    signature = "sha256=" + _sign("un-secret-partage", body)

    r = client.post("/api/v1/omnicanal/webhook/whatsapp",
                     content=body,
                     headers={"X-Hub-Signature-256": signature, "Content-Type": "application/json"})
    assert r.status_code == 202


def test_webhook_accepts_legacy_signature_format(client, monkeypatch):
    """Rétrocompatibilité : le format legacy X-Signature (plain hex) fonctionne aussi."""
    settings = get_settings()
    monkeypatch.setattr(settings, "social_webhook_secret", "un-secret-partage")

    body = json.dumps({
        "object": "whatsapp_business_account",
        "entry": [{
            "changes": [{
                "value": {
                    "messages": [{"from": "+21600000098", "type": "text", "text": {"body": "test legacy"}}],
                    "contacts": []
                }
            }]
        }]
    }).encode()
    signature = _sign("un-secret-partage", body)

    r = client.post("/api/v1/omnicanal/webhook/whatsapp",
                     content=body,
                     headers={"X-Signature": signature, "Content-Type": "application/json"})
    assert r.status_code == 202


def test_webhook_rejects_wrong_signature(client, monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "social_webhook_secret", "un-secret-partage")

    body = json.dumps({"object": "whatsapp_business_account", "entry": []}).encode()
    r = client.post("/api/v1/omnicanal/webhook/whatsapp",
                     content=body,
                     headers={"X-Hub-Signature-256": "sha256=" + "0" * 64,
                              "Content-Type": "application/json"})
    assert r.status_code == 401


def test_webhook_instagram_detected(client, monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "social_webhook_secret", "un-secret-partage")
    monkeypatch.setattr(settings, "instagram_enabled", True)

    body = json.dumps({
        "object": "instagram",
        "entry": [{
            "messaging": [{
                "sender": {"id": "ig_user_123"},
                "message": {"text": "Bonjour !", "mid": "ig_msg_001"}
            }]
        }]
    }).encode()
    signature = "sha256=" + _sign("un-secret-partage", body)

    r = client.post("/api/v1/omnicanal/webhook/instagram",
                     content=body,
                     headers={"X-Hub-Signature-256": signature, "Content-Type": "application/json"})
    assert r.status_code == 202


def test_webhook_tiktok_detected_by_header(client, monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "social_webhook_secret", "un-secret-partage")
    monkeypatch.setattr(settings, "tiktok_webhook_secret", "un-secret-partage")
    monkeypatch.setattr(settings, "tiktok_enabled", True)

    body = json.dumps({"event": {}, "timestamp": 1234567890}).encode()
    signature = _sign("un-secret-partage", body)

    r = client.post("/api/v1/omnicanal/webhook/tiktok",
                     content=body,
                     headers={"X-Tiktok-Signature": signature, "Content-Type": "application/json"})
    assert r.status_code == 202


def test_webhook_unknown_channel_fails(client, monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "social_webhook_secret", "un-secret-partage")

    body = json.dumps({"some_random": "data"}).encode()
    r = client.post("/api/v1/omnicanal/webhook/unknown",
                     content=body,
                     headers={"Content-Type": "application/json"})
    assert r.status_code == 400


def test_channel_status_endpoint(client, monkeypatch):
    """Test l'endpoint de statut des canaux (nécessite auth, donc on teste juste la route)."""
    # Sans auth, devrait retourner 401
    r = client.get("/api/v1/omnicanal/channels")
    assert r.status_code == 401
