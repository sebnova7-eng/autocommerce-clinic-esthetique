"""
AutoCommerce Clinic — API Authentification

N'existait pas : middleware/auth.py savait créer/décoder un JWT mais
aucune route n'exposait de moyen de se connecter. Ce fichier ajoute
login / refresh / me.
"""
from datetime import datetime
from typing import Union

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_db, limiter
from middleware.auth import (
    authenticate_user, create_tokens_for_user, decode_token,
    create_mfa_challenge_token, get_current_user, get_db_user,
    register_refresh_session, rotate_refresh_session, revoke_refresh_token,
)
from config import get_settings

router = APIRouter(prefix="/auth", tags=["auth"])
settings = get_settings()


# ── Schémas ────────────────────────────────────────────────

class LoginRequest(BaseModel):
    email: str
    password: str

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        if not v or "@" not in v:
            raise ValueError("Email invalide")
        return v.lower().strip()


class TokenResponse(BaseModel):
    access_token: str
    token_type: str
    expires_in: int


class MfaRequiredResponse(BaseModel):
    mfa_required: bool = True
    challenge_token: str


REFRESH_COOKIE_NAME = "autocommerce_refresh"


def _set_refresh_cookie(response: Response, refresh_token: str) -> None:
    response.set_cookie(
        key=REFRESH_COOKIE_NAME,
        value=refresh_token,
        max_age=settings.refresh_token_expire_days * 24 * 60 * 60,
        httponly=True,
        secure=settings.refresh_cookie_secure,
        samesite=settings.refresh_cookie_samesite,
        domain=settings.refresh_cookie_domain or None,
        path="/api",
    )


def _clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(
        key=REFRESH_COOKIE_NAME,
        domain=settings.refresh_cookie_domain or None,
        path="/api",
    )


def _public_tokens(response: Response, tokens: dict) -> dict:
    _set_refresh_cookie(response, tokens["refresh_token"])
    return {
        "access_token": tokens["access_token"],
        "token_type": tokens["token_type"],
        "expires_in": tokens["expires_in"],
    }


class UserOut(BaseModel):
    id: int
    email: str
    nom: str
    prenom: str
    role: str
    telephone: str | None = None
    specialite: str | None = None


# ── Routes ─────────────────────────────────────────────────

@router.post("/login", response_model=Union[TokenResponse, MfaRequiredResponse])
@limiter.limit("5/minute")
async def login(request: Request, response: Response, payload: LoginRequest, db: AsyncSession = Depends(get_db)):
    user = await authenticate_user(payload.email, payload.password, db)
    if not user:
        # Message générique volontaire : ne pas révéler si l'email existe.
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                             detail="Email ou mot de passe incorrect")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                             detail="Compte désactivé")

    # Si le MFA est activé, ne pas émettre les tokens tout de suite.
    # Le frontend doit appeler /auth/mfa/verify avec ce challenge_token +
    # l'OTP. Le token est signé et n'expose pas le user_id en clair côté
    # client (contrairement à l'ancien flux "MFA_REQUIRED" + lookup public
    # par email), et expire en 5 minutes.
    if user.mfa_enabled and user.mfa_secret:
        return MfaRequiredResponse(challenge_token=create_mfa_challenge_token(user.id))

    user.last_login = datetime.utcnow()
    await db.flush()

    tokens = create_tokens_for_user(user)
    await register_refresh_session(
        db, user, tokens["refresh_token"],
        user_agent=request.headers.get("user-agent"),
        ip_address=request.client.host if request.client else None,
    )
    return _public_tokens(response, tokens)


@router.post("/refresh", response_model=TokenResponse)
@limiter.limit("10/minute")
async def refresh(request: Request, response: Response, db: AsyncSession = Depends(get_db)):
    refresh_token = request.cookies.get(REFRESH_COOKIE_NAME)
    if not refresh_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token absent")
    token_payload = decode_token(refresh_token)
    if token_payload.get("type") != "refresh":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                             detail="Ce n'est pas un refresh token")

    user_id = token_payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token invalide")

    user = await get_db_user(int(user_id), db)
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                             detail="Utilisateur introuvable ou désactivé")

    try:
        tokens = await rotate_refresh_session(
            db, user, refresh_token,
            user_agent=request.headers.get("user-agent"),
            ip_address=request.client.host if request.client else None,
        )
    except HTTPException:
        _clear_refresh_cookie(response)
        raise
    return _public_tokens(response, tokens)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("20/minute")
async def logout(request: Request, response: Response, db: AsyncSession = Depends(get_db)):
    """Révoque le refresh token du cookie ; l’opération est idempotente."""
    refresh_token = request.cookies.get(REFRESH_COOKIE_NAME)
    if refresh_token:
        await revoke_refresh_token(db, refresh_token)
    _clear_refresh_cookie(response)
    return None


@router.get("/me", response_model=UserOut)
async def me(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentification requise",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user = await get_db_user(current_user["id"], db)
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Compte inactif ou introuvable")
    if int(user.clinic_id) != int(current_user["clinic_id"]) or str(user.role) != str(current_user.get("role")):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session obsolète")
    return UserOut(
        id=user.id, email=user.email, nom=user.nom, prenom=user.prenom,
        role=user.role, telephone=user.telephone, specialite=user.specialite,
    )
