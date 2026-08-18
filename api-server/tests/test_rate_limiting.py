"""Tests — rate limiting sur /auth/login et /auth/refresh

Le rate limiting est désactivé quand ENV=test (conftest.py) pour ne
pas rendre les autres tests flaky — on le réactive ici explicitement
le temps de vérifier qu'il fonctionne bien.
"""
import pytest
from fastapi.testclient import TestClient

from main import app
from api.deps import get_db, limiter
from middleware.auth import get_password_hash
from models.database import Utilisateur, RoleEnum


@pytest.fixture
def client_with_rate_limit(db):
    async def _override_get_db():
        yield db

    app.dependency_overrides[get_db] = _override_get_db
    limiter.enabled = True
    limiter.reset()
    yield TestClient(app)
    limiter.enabled = False
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_login_is_throttled_after_5_attempts_per_minute(client_with_rate_limit, db):
    user = Utilisateur(clinic_id=1, email="throttle@clinic.tn",
                        hashed_password=get_password_hash("MotDePasse!23"),
                        nom="X", prenom="Y", role=RoleEnum.MEDECIN.value, is_active=True)
    db.add(user)
    await db.flush()

    for _ in range(5):
        r = client_with_rate_limit.post("/api/v1/auth/login",
                                         json={"email": "throttle@clinic.tn", "password": "mauvais"})
        assert r.status_code == 401  # échecs normaux, pas encore throttled

    r = client_with_rate_limit.post("/api/v1/auth/login",
                                     json={"email": "throttle@clinic.tn", "password": "mauvais"})
    assert r.status_code == 429
