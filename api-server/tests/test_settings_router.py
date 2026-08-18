"""Tests — api/v1/settings.py (via TestClient)"""
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from main import app
from api.deps import get_db, limiter


@pytest.fixture
def client(db):
    async def _override_get_db():
        yield db

    app.dependency_overrides[get_db] = _override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_get_branding_is_public(client):
    r = client.get("/api/v1/settings/branding")
    assert r.status_code == 200
    assert "nom_clinique" in r.json()


def test_patch_branding_requires_auth(client):
    r = client.patch("/api/v1/settings/branding", json={"nom_clinique": "X"})
    assert r.status_code == 401


def test_public_reservation_endpoint_reachable_without_auth(client, medecin, acte):
    r = client.post("/api/v1/public/reservation", json={
        "nom": "Test", "prenom": "Public", "telephone": "+21699887766",
        "praticien_id": medecin.id, "acte_id": acte.id,
        "date_heure": (datetime(2026, 7, 20, 15, 0)).isoformat(),
    })
    assert r.status_code == 202
    assert r.json()["statut"] == "pending"
    assert "booking_request_id" in r.json()


@pytest.mark.asyncio
async def test_public_reservation_is_rate_limited(client, medecin, acte):
    limiter.enabled = True
    limiter.reset()
    try:
        for i in range(5):
            r = client.post("/api/v1/public/reservation", json={
                "nom": "Test", "prenom": "Public", "telephone": f"+2169988776{i}",
                "praticien_id": medecin.id, "acte_id": acte.id,
                "date_heure": (datetime(2026, 7, 20, 9, 0) + timedelta(hours=i)).isoformat(),
            })
            assert r.status_code == 202

        r = client.post("/api/v1/public/reservation", json={
            "nom": "Test", "prenom": "Public", "telephone": "+21699887799",
            "praticien_id": medecin.id, "acte_id": acte.id,
            "date_heure": (datetime(2026, 7, 20, 20, 0)).isoformat(),
        })
        assert r.status_code == 429
    finally:
        limiter.enabled = False
