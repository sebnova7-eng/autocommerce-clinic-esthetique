"""Tests — api/v1/auth.py (login, refresh, me)

Utilise l'app FastAPI réelle via TestClient + la base de test
(fixture `db`/`engine` de conftest) en surchargeant get_db pour que
la route utilise la même session que le test.
"""
import pytest
from fastapi.testclient import TestClient

from main import app
from api.deps import get_db
from middleware.auth import get_password_hash
from models.database import Utilisateur, RoleEnum


@pytest.fixture
def client(db):
    async def _override_get_db():
        yield db

    app.dependency_overrides[get_db] = _override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
async def user_with_password(db):
    user = Utilisateur(
        clinic_id=1, email="login@clinic.tn",
        hashed_password=get_password_hash("MotDePasse!23"),
        nom="Ferjani", prenom="Yassine", role=RoleEnum.MEDECIN.value,
        is_active=True,
    )
    db.add(user)
    await db.flush()
    return user


def test_login_success_returns_tokens(client, user_with_password):
    r = client.post("/api/v1/auth/login", json={"email": "login@clinic.tn", "password": "MotDePasse!23"})
    assert r.status_code == 200
    body = r.json()
    assert "access_token" in body and "refresh_token" not in body
    assert body["token_type"] == "bearer"
    set_cookie = r.headers.get("set-cookie", "")
    assert "autocommerce_refresh=" in set_cookie
    assert "HttpOnly" in set_cookie
    assert "SameSite=lax" in set_cookie
    assert "Path=/api" in set_cookie


def test_login_wrong_password_returns_401(client, user_with_password):
    r = client.post("/api/v1/auth/login", json={"email": "login@clinic.tn", "password": "mauvais"})
    assert r.status_code == 401


def test_login_unknown_email_returns_401_not_404(client):
    """Message générique : ne pas révéler que l'email n'existe pas."""
    r = client.post("/api/v1/auth/login", json={"email": "inconnu@clinic.tn", "password": "x"})
    assert r.status_code == 401


async def test_login_inactive_user_returns_403(client, db):
    user = Utilisateur(
        clinic_id=1, email="inactif@clinic.tn",
        hashed_password=get_password_hash("MotDePasse!23"),
        nom="X", prenom="Y", role=RoleEnum.MEDECIN.value, is_active=False,
    )
    db.add(user)
    await db.flush()

    r = client.post("/api/v1/auth/login", json={"email": "inactif@clinic.tn", "password": "MotDePasse!23"})
    assert r.status_code == 403


def test_me_requires_authentication(client):
    r = client.get("/api/v1/auth/me")
    assert r.status_code == 401


def test_me_returns_current_user(client, user_with_password):
    login = client.post("/api/v1/auth/login", json={"email": "login@clinic.tn", "password": "MotDePasse!23"})
    token = login.json()["access_token"]
    r = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json()["email"] == "login@clinic.tn"


def test_refresh_with_access_token_is_rejected(client, user_with_password):
    login = client.post("/api/v1/auth/login", json={"email": "login@clinic.tn", "password": "MotDePasse!23"})
    access_token = login.json()["access_token"]
    r = client.post("/api/v1/auth/refresh", cookies={"autocommerce_refresh": access_token})
    assert r.status_code == 401


def test_refresh_with_valid_refresh_token_issues_new_access_token(client, user_with_password):
    login = client.post("/api/v1/auth/login", json={"email": "login@clinic.tn", "password": "MotDePasse!23"})
    refresh_token = login.cookies.get("autocommerce_refresh")
    assert refresh_token
    r = client.post("/api/v1/auth/refresh", cookies={"autocommerce_refresh": refresh_token})
    assert r.status_code == 200
    assert "access_token" in r.json()


def test_refresh_rejects_garbage_token(client):
    r = client.post("/api/v1/auth/refresh", cookies={"autocommerce_refresh": "not-a-real-token"})
    assert r.status_code == 401


# ── MFA : login émet un challenge_token, plus jamais de user_id en clair ──

@pytest.fixture
async def user_with_mfa(db):
    import pyotp
    secret = pyotp.random_base32()
    user = Utilisateur(
        clinic_id=1, email="mfa-login@clinic.tn",
        hashed_password=get_password_hash("MotDePasse!23"),
        nom="Dridi", prenom="Salma", role=RoleEnum.MEDECIN.value,
        is_active=True, mfa_enabled=True, mfa_secret=secret,
    )
    db.add(user)
    await db.flush()
    return user, secret


def test_login_with_mfa_enabled_returns_challenge_token_not_tokens(client, user_with_mfa):
    user, _ = user_with_mfa
    r = client.post("/api/v1/auth/login", json={"email": user.email, "password": "MotDePasse!23"})
    assert r.status_code == 200
    body = r.json()
    assert body["mfa_required"] is True
    assert "challenge_token" in body
    assert "access_token" not in body


def test_mfa_verify_with_valid_challenge_and_otp_returns_tokens(client, user_with_mfa):
    import pyotp
    user, secret = user_with_mfa
    login = client.post("/api/v1/auth/login", json={"email": user.email, "password": "MotDePasse!23"})
    challenge_token = login.json()["challenge_token"]

    otp = pyotp.TOTP(secret).now()
    r = client.post("/api/v1/auth/mfa/verify", json={"challenge_token": challenge_token, "otp": otp})
    assert r.status_code == 200
    assert "access_token" in r.json()
    assert "refresh_token" not in r.json()
    assert "HttpOnly" in r.headers.get("set-cookie", "")


def test_mfa_verify_rejects_garbage_challenge_token(client):
    r = client.post("/api/v1/auth/mfa/verify", json={"challenge_token": "not-a-real-token", "otp": "000000"})
    assert r.status_code == 401


def test_mfa_verify_rejects_access_token_as_challenge(client, user_with_mfa):
    """Un access_token classique (type=access) ne doit pas être accepté
    comme challenge MFA (type=mfa_challenge attendu)."""
    user, _ = user_with_mfa
    user.mfa_enabled = False
    r = client.post("/api/v1/auth/login", json={"email": user.email, "password": "MotDePasse!23"})
    access_token = r.json()["access_token"]
    r2 = client.post("/api/v1/auth/mfa/verify", json={"challenge_token": access_token, "otp": "000000"})
    assert r2.status_code == 401


def test_mfa_info_endpoint_no_longer_exists(client):
    """L'ancienne route publique d'énumération est bien supprimée."""
    r = client.get("/api/v1/auth/mfa/info/whoever@clinic.tn")
    assert r.status_code == 404


# ── Bloc 3 : rotation, révocation et détection de réutilisation ─────────────
def test_refresh_rotation_invalidates_old_token_and_issues_new_one(client, user_with_password):
    login = client.post("/api/v1/auth/login", json={"email": "login@clinic.tn", "password": "MotDePasse!23"})
    old_refresh = login.cookies.get("autocommerce_refresh")
    assert old_refresh
    rotated = client.post("/api/v1/auth/refresh", cookies={"autocommerce_refresh": old_refresh})
    assert rotated.status_code == 200
    new_refresh = rotated.cookies.get("autocommerce_refresh")
    assert new_refresh and new_refresh != old_refresh
    replay = client.post("/api/v1/auth/refresh", cookies={"autocommerce_refresh": old_refresh})
    assert replay.status_code == 401
    assert "réutilisation" in replay.json()["detail"].lower()
    assert client.post("/api/v1/auth/refresh", cookies={"autocommerce_refresh": new_refresh}).status_code == 401


def test_logout_revokes_refresh_token(client, user_with_password):
    login = client.post("/api/v1/auth/login", json={"email": "login@clinic.tn", "password": "MotDePasse!23"})
    refresh_token = login.cookies.get("autocommerce_refresh")
    assert refresh_token
    logout = client.post("/api/v1/auth/logout", cookies={"autocommerce_refresh": refresh_token})
    assert logout.status_code == 204
    assert client.post("/api/v1/auth/refresh", cookies={"autocommerce_refresh": refresh_token}).status_code == 401


def test_expired_refresh_token_is_rejected(client, user_with_password):
    from datetime import timedelta
    from middleware.auth import create_access_token
    expired = create_access_token(
        {"sub": str(user_with_password.id), "type": "refresh", "jti": "expired-jti", "family_id": "expired-family"},
        expires_delta=timedelta(seconds=-1),
    )
    assert client.post("/api/v1/auth/refresh", cookies={"autocommerce_refresh": expired}).status_code == 401


def test_refresh_with_invalid_signature_is_rejected(client, user_with_password):
    login = client.post("/api/v1/auth/login", json={"email": "login@clinic.tn", "password": "MotDePasse!23"})
    token = login.cookies.get("autocommerce_refresh")
    assert token
    tampered = token[:-1] + ("a" if token[-1] != "a" else "b")
    response = client.post("/api/v1/auth/refresh", cookies={"autocommerce_refresh": tampered})
    assert response.status_code == 401
