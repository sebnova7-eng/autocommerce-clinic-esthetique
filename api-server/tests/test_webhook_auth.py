"""Tests — middleware/webhook_auth.py + endpoint /social/messages/webhook"""
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

    r = client.post("/api/v1/social/messages/webhook",
                     json={"plateforme": "whatsapp", "contact_id": "x", "contenu": "test"})
    assert r.status_code == 503


def test_webhook_rejects_missing_signature(client, monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "social_webhook_secret", "un-secret-partage")

    r = client.post("/api/v1/social/messages/webhook",
                     json={"plateforme": "whatsapp", "contact_id": "x", "contenu": "test"})
    assert r.status_code == 401


def test_webhook_rejects_wrong_signature(client, monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "social_webhook_secret", "un-secret-partage")

    r = client.post("/api/v1/social/messages/webhook",
                     json={"plateforme": "whatsapp", "contact_id": "x", "contenu": "test"},
                     headers={"X-Signature": "0" * 64})
    assert r.status_code == 401


def test_webhook_accepts_valid_signature(client, monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "social_webhook_secret", "un-secret-partage")
    monkeypatch.setattr(settings, "social_webhook_clinic_id", 1)

    body = json.dumps({"plateforme": "whatsapp", "contact_id": "+21600000099", "contenu": "vos horaires ?"}).encode()
    signature = _sign("un-secret-partage", body)

    r = client.post("/api/v1/social/messages/webhook", content=body,
                     headers={"X-Signature": signature, "Content-Type": "application/json"})
    assert r.status_code == 201
