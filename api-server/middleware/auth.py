"""
AutoCommerce Clinic — Authentification JWT
PyJWT 2.10.1 (jamais python-jose)
"""

from datetime import datetime, timedelta
from hashlib import sha256
from typing import Optional
from uuid import uuid4

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from passlib.context import CryptContext
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from config import get_settings
from models.database import Utilisateur
from models.security import RefreshTokenSession
from middleware.clinic_context import set_clinic_id


settings = get_settings()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer(auto_error=False)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=settings.access_token_expire_minutes))
    to_encode.update({"exp": expire})
    encoded = jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)
    return encoded


def create_mfa_challenge_token(user_id: int) -> str:
    return create_access_token(
        {"sub": str(user_id), "type": "mfa_challenge"},
        expires_delta=timedelta(minutes=5),
    )


def decode_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expiré")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Token invalide")


async def get_db_user(user_id: int, db: AsyncSession) -> Optional[Utilisateur]:
    result = await db.execute(select(Utilisateur).where(Utilisateur.id == user_id))
    return result.scalar_one_or_none()


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> Optional[dict]:
    """Retourne un dict sérialisé depuis le JWT d'accès.

    Le contrat consommé par l'application est un mapping simple
    (`current_user["id"]`, `current_user.get("role")`, etc.). Repartir du
    payload évite d'ouvrir une nouvelle session DB hors chaîne de dépendances
    FastAPI, ce qui cassait les tests qui surchargent `get_db` avec une base
    SQLite éphémère partagée.
    """
    if not credentials:
        return None

    payload = decode_token(credentials.credentials)

    if payload.get("type") != "access":
        raise HTTPException(status_code=401, detail="Type de token invalide")

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Token sans identifiant utilisateur")

    clinic_id = payload.get("clinic_id")
    if not isinstance(clinic_id, int) or clinic_id <= 0:
        raise HTTPException(status_code=401, detail="Token sans clinique valide")

    return {
        "id": int(user_id),
        "role": payload.get("role"),
        "clinic_id": clinic_id,
        "email": payload.get("email"),
        "nom": payload.get("nom"),
        "prenom": payload.get("prenom"),
        "is_active": payload.get("is_active", True),
    }


async def _auth_db_dependency():
    """Résout la session DB sans importer api.deps au chargement du module.

    Le lazy import évite le cycle `api.deps -> middleware.auth -> api.deps`.
    """
    from api.deps import get_db
    async for db in get_db():
        yield db


async def get_current_active_user(
    user: Optional[dict] = Depends(get_current_user),
    db: AsyncSession = Depends(_auth_db_dependency),
) -> dict:
    """Revalide le JWT contre l’utilisateur courant en base.

    Un access token contient des claims pour le routage, mais les privilèges et
    l’état actif de l’utilisateur ne sont jamais considérés comme définitifs.
    Cela permet de révoquer immédiatement un compte ou un changement de rôle.
    """
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentification requise",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not isinstance(db, AsyncSession):
        # Compatibilité des appels unitaires directs ; les routes FastAPI
        # injectent toujours une vraie session via _auth_db_dependency.
        if not user.get("is_active"):
            raise HTTPException(status_code=403, detail="Compte inactif")
        set_clinic_id(int(user["clinic_id"]))
        return user

    db_user = await get_db_user(int(user["id"]), db)
    if not db_user:
        raise HTTPException(status_code=401, detail="Compte introuvable")
    if not db_user.is_active:
        raise HTTPException(status_code=403, detail="Compte inactif")
    if int(db_user.clinic_id) != int(user.get("clinic_id", 0)):
        raise HTTPException(status_code=401, detail="Contexte clinique invalide")
    if str(db_user.role) != str(user.get("role")):
        raise HTTPException(status_code=401, detail="Rôle du token obsolète")

    set_clinic_id(int(db_user.clinic_id))
    return {
        "id": db_user.id,
        "role": db_user.role,
        "clinic_id": db_user.clinic_id,
        "email": db_user.email,
        "nom": db_user.nom,
        "prenom": db_user.prenom,
        "is_active": db_user.is_active,
    }


async def authenticate_user(email: str, password: str, db: AsyncSession) -> Optional[Utilisateur]:
    result = await db.execute(select(Utilisateur).where(Utilisateur.email == email))
    user = result.scalar_one_or_none()
    if not user or not verify_password(password, user.hashed_password):
        return None
    return user


def _hash_token(token: str) -> str:
    return sha256(token.encode("utf-8")).hexdigest()


def create_refresh_token(user: Utilisateur, family_id: Optional[str] = None) -> str:
    return create_access_token(
        {
            "sub": str(user.id),
            "type": "refresh",
            "jti": uuid4().hex,
            "family_id": family_id or uuid4().hex,
        },
        expires_delta=timedelta(days=settings.refresh_token_expire_days),
    )


def create_tokens_for_user(user: Utilisateur, family_id: Optional[str] = None) -> dict:
    access_payload = {
        "sub": str(user.id),
        "email": user.email,
        "role": user.role,
        "clinic_id": user.clinic_id,
        "nom": user.nom,
        "prenom": user.prenom,
        "is_active": user.is_active,
        "type": "access",
    }
    return {
        "access_token": create_access_token(access_payload),
        "refresh_token": create_refresh_token(user, family_id=family_id),
        "token_type": "bearer",
        "expires_in": settings.access_token_expire_minutes * 60,
    }


async def register_refresh_session(
    db: AsyncSession,
    user: Utilisateur,
    refresh_token: str,
    *,
    user_agent: Optional[str] = None,
    ip_address: Optional[str] = None,
) -> RefreshTokenSession:
    payload = decode_token(refresh_token)
    now = datetime.utcnow()
    session = RefreshTokenSession(
        utilisateur_id=user.id,
        jti=payload["jti"],
        family_id=payload["family_id"],
        token_hash=_hash_token(refresh_token),
        issued_at=now,
        expires_at=datetime.fromtimestamp(payload["exp"]),
        user_agent=user_agent,
        ip_address=ip_address,
    )
    db.add(session)
    await db.flush()
    return session


async def revoke_refresh_family(db: AsyncSession, family_id: str, now: Optional[datetime] = None) -> None:
    now = now or datetime.utcnow()
    await db.execute(
        update(RefreshTokenSession)
        .where(
            RefreshTokenSession.family_id == family_id,
            RefreshTokenSession.revoked_at.is_(None),
        )
        .values(revoked_at=now, reuse_detected_at=now)
    )


async def rotate_refresh_session(
    db: AsyncSession,
    user: Utilisateur,
    refresh_token: str,
    *,
    user_agent: Optional[str] = None,
    ip_address: Optional[str] = None,
) -> dict:
    payload = decode_token(refresh_token)
    if payload.get("type") != "refresh" or not payload.get("jti") or not payload.get("family_id"):
        raise HTTPException(status_code=401, detail="Refresh token invalide")
    session = await db.scalar(
        select(RefreshTokenSession).where(RefreshTokenSession.jti == payload["jti"])
    )
    if not session or session.utilisateur_id != user.id:
        raise HTTPException(status_code=401, detail="Refresh token révoqué ou inconnu")
    now = datetime.utcnow()
    if session.revoked_at is not None:
        await revoke_refresh_family(db, session.family_id, now)
        await db.flush()
        raise HTTPException(status_code=401, detail="Réutilisation de refresh token détectée")
    if session.expires_at <= now or session.token_hash != _hash_token(refresh_token):
        raise HTTPException(status_code=401, detail="Refresh token invalide")
    tokens = create_tokens_for_user(user, family_id=session.family_id)
    new_session = await register_refresh_session(
        db, user, tokens["refresh_token"], user_agent=user_agent, ip_address=ip_address
    )
    session.revoked_at = now
    session.replaced_by_jti = new_session.jti
    await db.flush()
    return tokens


async def revoke_refresh_token(db: AsyncSession, refresh_token: str) -> bool:
    try:
        payload = decode_token(refresh_token)
    except HTTPException:
        return False
    if payload.get("type") != "refresh" or not payload.get("jti"):
        return False
    session = await db.scalar(
        select(RefreshTokenSession).where(RefreshTokenSession.jti == payload["jti"])
    )
    if not session or session.token_hash != _hash_token(refresh_token):
        return False
    if session.revoked_at is None:
        session.revoked_at = datetime.utcnow()
        await db.flush()
    return True
