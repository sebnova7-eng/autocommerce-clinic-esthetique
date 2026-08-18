"""Tests — middleware/auth.py"""
from datetime import timedelta

import jwt
import pytest
from fastapi import HTTPException

from middleware.auth import (
    verify_password, get_password_hash, create_access_token,
    decode_token, get_current_user, get_current_active_user,
)


def test_password_hash_roundtrip():
    hashed = get_password_hash("MotDePasse!23")
    assert hashed != "MotDePasse!23"
    assert verify_password("MotDePasse!23", hashed)


def test_password_hash_rejects_wrong_password():
    hashed = get_password_hash("MotDePasse!23")
    assert not verify_password("MauvaisMotDePasse", hashed)


def test_password_hash_is_salted_differently_each_time():
    h1 = get_password_hash("same-password")
    h2 = get_password_hash("same-password")
    assert h1 != h2  # bcrypt salage


def test_create_and_decode_token_roundtrip():
    token = create_access_token({"sub": "42", "email": "a@b.com", "role": "medecin"})
    payload = decode_token(token)
    assert payload["sub"] == "42"
    assert payload["role"] == "medecin"


def test_decode_expired_token_raises_401():
    token = create_access_token({"sub": "1"}, expires_delta=timedelta(seconds=-10))
    with pytest.raises(HTTPException) as exc:
        decode_token(token)
    assert exc.value.status_code == 401


def test_decode_invalid_token_raises_401():
    with pytest.raises(HTTPException) as exc:
        decode_token("not.a.valid.jwt")
    assert exc.value.status_code == 401


def test_decode_token_signed_with_wrong_key_is_rejected():
    forged = jwt.encode({"sub": "1"}, "une-autre-cle-de-test-de-32-caracteres-minimum", algorithm="HS256")
    with pytest.raises(HTTPException) as exc:
        decode_token(forged)
    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_get_current_user_returns_none_without_credentials():
    user = await get_current_user(credentials=None)
    assert user is None


@pytest.mark.asyncio
async def test_get_current_active_user_raises_401_when_no_user():
    with pytest.raises(HTTPException) as exc:
        await get_current_active_user(user=None)
    assert exc.value.status_code == 401


from unittest.mock import AsyncMock, MagicMock, patch
from models.database import Utilisateur

@pytest.mark.asyncio
async def test_token_returns_user_dict():
    """get_current_user doit retourner un dict — c'est le contrat attendu
    par la quasi-totalité de l'app (current_user["id"], .get("role")...).
    Un objet ORM ici casse silencieusement patients/commissions/agenda/
    factures/social/recrutement/dossiers_medicaux (AttributeError: 'dict'
    object a un .get() mais un objet Utilisateur non)."""
    class FakeCreds:
        credentials = create_access_token({"sub": "7", "role": "medecin", "clinic_id": 1, "type": "access"})

    mock_user = MagicMock(spec=Utilisateur)
    mock_user.id = 7
    mock_user.clinic_id = 1
    mock_user.role = "medecin"
    mock_user.email = "medecin@clinic.tn"
    mock_user.nom = "Trabelsi"
    mock_user.prenom = "Sami"
    mock_user.is_active = True

    with patch("middleware.auth.get_db_user", new_callable=AsyncMock) as mock_get_db_user:
        mock_get_db_user.return_value = mock_user
        user = await get_current_user(credentials=FakeCreds())
        assert isinstance(user, dict)
        assert user["id"] == 7
        assert user["clinic_id"] == 1
        assert user.get("role") == "medecin"


@pytest.mark.asyncio
async def test_token_missing_sub_raises_401():
    class FakeCreds:
        credentials = create_access_token({"role": "medecin", "type": "access"})

    with pytest.raises(HTTPException) as exc:
        await get_current_user(credentials=FakeCreds())
    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_refresh_token_rejected_by_get_current_user():
    """Un refresh token (durée de vie longue) ne doit jamais donner accès
    aux routes protégées — seul /auth/refresh doit l'accepter."""
    class FakeCreds:
        credentials = create_access_token({"sub": "7", "type": "refresh"})

    with pytest.raises(HTTPException) as exc:
        await get_current_user(credentials=FakeCreds())
    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_token_without_type_rejected_by_get_current_user():
    """Un ancien token émis avant l'ajout du champ "type", ou un token
    forgé sans ce champ, doit être refusé plutôt qu'accepté par défaut."""
    class FakeCreds:
        credentials = create_access_token({"sub": "7", "role": "medecin"})

    with pytest.raises(HTTPException) as exc:
        await get_current_user(credentials=FakeCreds())
    assert exc.value.status_code == 401
