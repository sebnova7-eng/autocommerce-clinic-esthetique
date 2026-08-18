"""
AutoCommerce Clinic — API MFA (Multi-Factor Authentication)

Routes :
  POST /auth/mfa/setup        → Génère secret TOTP + QR + backup codes
  POST /auth/mfa/confirm      → Vérifie le premier OTP et active le MFA
  POST /auth/mfa/verify       → Vérifie l'OTP lors de la connexion (étape 2)
  POST /auth/mfa/disable      → Désactive le MFA (mot de passe requis)
  GET  /auth/mfa/status       → Vérifie si le MFA est activé
"""
import json
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_db, limiter
from config import get_settings
from api.v1.auth import _public_tokens
from middleware.auth import (
    create_tokens_for_user,
    decode_token,
    get_current_active_user,
    get_db_user,
    register_refresh_session,
)
from services.mfa import (
    MAX_MFA_ATTEMPTS,
    generate_backup_codes,
    generate_qr_code,
    get_totp_uri,
    verify_backup_code,
    verify_totp,
    generate_mfa_secret,
    hash_backup_codes,
)

settings = get_settings()
router = APIRouter(prefix="/auth/mfa", tags=["mfa"])


# ── Schémas ────────────────────────────────────────────────

class MfaSetupResponse(BaseModel):
    secret: str
    qr_uri: str
    qr_code_b64: str
    backup_codes: list[str]


class MfaConfirmRequest(BaseModel):
    otp: str


class MfaVerifyRequest(BaseModel):
    otp: str
    challenge_token: str  # émis par /auth/login, remplace l'ancien user_id en clair


class MfaVerifyResponse(BaseModel):
    access_token: str
    token_type: str
    expires_in: int


class MfaDisableRequest(BaseModel):
    password: str


class MfaStatusResponse(BaseModel):
    enabled: bool
    setup_at: str | None = None


class MfaInfoResponse(BaseModel):
    user_id: int
    mfa_enabled: bool


# ── Routes ─────────────────────────────────────────────────

@router.post("/setup", response_model=MfaSetupResponse)
async def mfa_setup(
    request: Request,
    current_user: dict = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Génère un nouveau secret TOTP + QR code + codes de secours.
    
    L'utilisateur doit déjà être authentifié. Le MFA n'est pas encore
    activé : il doit confirmer avec son premier OTP via /mfa/confirm.
    """
    user = await get_db_user(current_user["id"], db)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Utilisateur introuvable")

    # Générer le secret
    secret = generate_mfa_secret()
    branding_context = {"clinic_name": "Clinique"}  # Fallback
    try:
        from services.branding import get_branding_context
        branding_context = await get_branding_context(db)
    except Exception:
        pass

    clinic_name = branding_context["clinic_name"]
    uri = get_totp_uri(secret, user.email, clinic_name)
    qr_bytes = generate_qr_code(uri)

    import base64
    qr_b64 = base64.b64encode(qr_bytes).decode("utf-8")

    # Générer les codes de secours
    backup_codes = generate_backup_codes()
    backup_code_hashes = hash_backup_codes(backup_codes)

    # Stocker temporairement uniquement les hashes (pas encore activé).
    user.mfa_secret = secret
    user.mfa_backup_codes = json.dumps(backup_code_hashes)
    await db.flush()

    return MfaSetupResponse(
        secret=secret,
        qr_uri=uri,
        qr_code_b64=qr_b64,
        backup_codes=backup_codes,
    )


@router.post("/confirm")
async def mfa_confirm(
    request: Request,
    payload: MfaConfirmRequest,
    current_user: dict = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Confirme l'activation du MFA avec le premier OTP valide."""
    user = await get_db_user(current_user["id"], db)
    if not user or not user.mfa_secret:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Aucune configuration MFA en cours. Appelez /setup d'abord."
        )

    if user.mfa_enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Le MFA est déjà activé."
        )

    # Vérifier le code OTP
    if not verify_totp(user.mfa_secret, payload.otp):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Code OTP invalide. Vérifiez votre application d'authentification."
        )

    # Activer le MFA
    user.mfa_enabled = True
    user.mfa_setup_at = datetime.utcnow()
    user.mfa_failed_attempts = 0
    user.mfa_locked_until = None
    await db.flush()

    return {"message": "MFA activé avec succès", "mfa_enabled": True}


@router.post("/verify", response_model=MfaVerifyResponse)
@limiter.limit("10/minute")
async def mfa_verify(
    request: Request,
    response: Response,
    payload: MfaVerifyRequest,
    db: AsyncSession = Depends(get_db),
):
    """Vérifie le code OTP après une première étape d'authentification.
    
    C'est l'étape 2 du login : après avoir vérifié email+password,
    le frontend appelle cette route avec le challenge_token reçu de
    /auth/login et le code OTP pour obtenir les tokens d'accès.
    """
    try:
        challenge = decode_token(payload.challenge_token)
    except HTTPException:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Challenge MFA invalide ou expiré")
    if challenge.get("type") != "mfa_challenge":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Challenge MFA invalide")
    try:
        user_id = int(challenge["sub"])
    except (KeyError, ValueError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Challenge MFA invalide")

    user = await get_db_user(user_id, db)
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Utilisateur introuvable ou désactivé")

    if not user.mfa_enabled or not user.mfa_secret:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Le MFA n'est pas activé pour cet utilisateur."
        )

    # Vérifier le verrouillage
    if user.mfa_locked_until and user.mfa_locked_until > datetime.utcnow():
        remaining = int((user.mfa_locked_until - datetime.utcnow()).total_seconds() / 60)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Trop de tentatives MFA. Réessayez dans {remaining} minutes."
        )

    # Vérifier le code OTP
    otp_valid = verify_totp(user.mfa_secret, payload.otp)

    # Vérifier les codes de secours si OTP invalide
    if not otp_valid and user.mfa_backup_codes:
        try:
            backup_codes = json.loads(user.mfa_backup_codes)
            if verify_backup_code(payload.otp, backup_codes):
                # Supprimer le hash correspondant : un code est mono-usage.
                remaining_codes = []
                consumed = False
                for stored_code in backup_codes:
                    if not consumed and verify_backup_code(payload.otp, [stored_code]):
                        consumed = True
                    else:
                        remaining_codes.append(stored_code)
                user.mfa_backup_codes = json.dumps(remaining_codes) if remaining_codes else None
                otp_valid = consumed
        except (json.JSONDecodeError, TypeError):
            pass

    if not otp_valid:
        # Incrémenter les tentatives échouées
        user.mfa_failed_attempts = (user.mfa_failed_attempts or 0) + 1
        if user.mfa_failed_attempts >= MAX_MFA_ATTEMPTS:
            # Verrouiller pour 15 minutes
            user.mfa_locked_until = datetime.utcnow() + timedelta(minutes=15)
            user.mfa_failed_attempts = 0
            await db.flush()
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Trop de tentatives. Compte verrouillé pour 15 minutes."
            )
        await db.flush()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Code invalide. Veuillez réessayer."
        )

    # Réinitialiser les tentatives
    user.mfa_failed_attempts = 0
    user.mfa_locked_until = None
    user.last_login = datetime.utcnow()
    await db.flush()

    tokens = create_tokens_for_user(user)
    await register_refresh_session(
        db, user, tokens["refresh_token"],
        user_agent=request.headers.get("user-agent"),
        ip_address=request.client.host if request.client else None,
    )
    return _public_tokens(response, tokens)


@router.post("/disable")
async def mfa_disable(
    request: Request,
    payload: MfaDisableRequest,
    current_user: dict = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Désactive le MFA. Nécessite le mot de passe pour confirmation."""
    user = await get_db_user(current_user["id"], db)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Utilisateur introuvable")

    # Vérifier le mot de passe
    from middleware.auth import verify_password
    if not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Mot de passe incorrect"
        )

    if not user.mfa_enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Le MFA n'est pas activé."
        )

    # Désactiver le MFA
    user.mfa_enabled = False
    user.mfa_secret = None
    user.mfa_backup_codes = None
    user.mfa_setup_at = None
    user.mfa_failed_attempts = 0
    user.mfa_locked_until = None
    await db.flush()

    return {"message": "MFA désactivé", "mfa_enabled": False}


@router.get("/status", response_model=MfaStatusResponse)
async def mfa_status(
    current_user: dict = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Vérifie le statut du MFA de l'utilisateur connecté."""
    user = await get_db_user(current_user["id"], db)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Utilisateur introuvable")

    return MfaStatusResponse(
        enabled=user.mfa_enabled,
        setup_at=user.mfa_setup_at.isoformat() if user.mfa_setup_at else None,
    )
