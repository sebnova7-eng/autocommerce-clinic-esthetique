"""API Assistant / Agent WhatsApp — Blocs 2, 3 et 4."""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_db
from middleware.assistant_whitelist import ensure_can_receive_assistant_message, normalize_numero
from middleware.clinic_rbac import require_role
from models.database import RoleEnum, Utilisateur
from models.security import AlerteSecurite, CommandeAssistant, NumeroWhitelist
from services.assistant_ia import handle_whatsapp_message
from services.assistant_security import revoke_whitelist_access, rotate_whitelist_access
from services.clinic_agent import handle_agent_message

router = APIRouter(prefix="/assistant", tags=["assistant"])


class WhitelistAddRequest(BaseModel):
    numero: str = Field(..., min_length=4, max_length=20)
    utilisateur_id: int
    nom: Optional[str] = None
    expires_at: Optional[datetime] = None


class WhitelistOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    numero: str
    nom: Optional[str] = None
    utilisateur_id: Optional[int] = None
    statut: str
    expires_at: Optional[datetime] = None
    revoked_at: Optional[datetime] = None
    last_key_rotation: Optional[datetime] = None
    created_at: datetime


class CommandeAssistantOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    numero: str
    utilisateur_id: Optional[int] = None
    question: Optional[str] = None
    intent_detecte: Optional[str] = None
    outil_appele: Optional[str] = None
    reponse: Optional[str] = None
    statut: str
    role_applique: Optional[str] = None
    raison_refus: Optional[str] = None
    created_at: datetime


class AlerteSecuriteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    type_alerte: str
    severite: str
    statut: str
    description: str
    numero_concerne: Optional[str] = None
    utilisateur_id: Optional[int] = None
    created_at: datetime


class TestMessageRequest(BaseModel):
    numero: str
    question: str


class RevokeRequest(BaseModel):
    raison: str = Field(..., min_length=3, max_length=300)


@router.post("/whitelist", response_model=WhitelistOut)
async def api_whitelist_add(
    payload: WhitelistAddRequest,
    current_user: Utilisateur = Depends(require_role(RoleEnum.ADMIN, RoleEnum.DIRECTRICE)),
    db: AsyncSession = Depends(get_db),
):
    numero = await normalize_numero(payload.numero)

    user_res = await db.execute(select(Utilisateur).where(Utilisateur.id == payload.utilisateur_id, Utilisateur.clinic_id == current_user["clinic_id"]))
    user = user_res.scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(400, "Utilisateur lié introuvable ou inactif")

    existing_res = await db.execute(select(NumeroWhitelist).where(NumeroWhitelist.numero == numero, NumeroWhitelist.clinic_id == current_user["clinic_id"]))
    existing = existing_res.scalar_one_or_none()
    if existing:
        existing.utilisateur_id = payload.utilisateur_id
        existing.nom = payload.nom
        existing.expires_at = payload.expires_at
        existing.statut = "active"
        existing.revoked_at = None
        existing.raison_revocation = None
        row = existing
    else:
        row = NumeroWhitelist(
            clinic_id=current_user["clinic_id"],
            numero=numero,
            utilisateur_id=payload.utilisateur_id,
            nom=payload.nom,
            expires_at=payload.expires_at,
            statut="active",
        )
        db.add(row)
    await db.flush()
    return row


@router.get("/whitelist", response_model=List[WhitelistOut])
async def api_whitelist_list(
    current_user: Utilisateur = Depends(require_role(RoleEnum.ADMIN, RoleEnum.DIRECTRICE)),
    db: AsyncSession = Depends(get_db),
):
    rows = (await db.execute(select(NumeroWhitelist).where(NumeroWhitelist.clinic_id == current_user["clinic_id"]).order_by(NumeroWhitelist.created_at.desc()))).scalars().all()
    return list(rows)


@router.post("/whitelist/{numero}/rotate", response_model=WhitelistOut)
async def api_whitelist_rotate(
    numero: str,
    current_user: Utilisateur = Depends(require_role(RoleEnum.ADMIN, RoleEnum.DIRECTRICE)),
    db: AsyncSession = Depends(get_db),
):
    row = await rotate_whitelist_access(numero, current_user["id"], db, clinic_id=current_user["clinic_id"])
    return row


@router.post("/whitelist/{numero}/revoke", response_model=WhitelistOut)
async def api_whitelist_revoke(
    numero: str,
    payload: RevokeRequest,
    current_user: Utilisateur = Depends(require_role(RoleEnum.ADMIN, RoleEnum.DIRECTRICE)),
    db: AsyncSession = Depends(get_db),
):
    row = await revoke_whitelist_access(numero, current_user["id"], payload.raison, db, clinic_id=current_user["clinic_id"])
    return row


@router.get("/commandes", response_model=List[CommandeAssistantOut])
async def api_commandes(
    limit: int = Query(100, ge=1, le=500),
    numero: Optional[str] = Query(None),
    current_user: Utilisateur = Depends(require_role(RoleEnum.ADMIN, RoleEnum.DIRECTRICE)),
    db: AsyncSession = Depends(get_db),
):
    query = select(CommandeAssistant).where(CommandeAssistant.clinic_id == current_user["clinic_id"])
    if numero:
        query = query.where(CommandeAssistant.numero == await normalize_numero(numero))
    query = query.order_by(desc(CommandeAssistant.created_at)).limit(limit)
    rows = (await db.execute(query)).scalars().all()
    return list(rows)


@router.get("/alertes", response_model=List[AlerteSecuriteOut])
async def api_alertes(
    limit: int = Query(100, ge=1, le=500),
    current_user: Utilisateur = Depends(require_role(RoleEnum.ADMIN, RoleEnum.DIRECTRICE)),
    db: AsyncSession = Depends(get_db),
):
    rows = (await db.execute(select(AlerteSecurite).where(AlerteSecurite.clinic_id == current_user["clinic_id"]).order_by(desc(AlerteSecurite.created_at)).limit(limit))).scalars().all()
    return list(rows)


@router.post("/test-message")
async def api_test_message(
    payload: TestMessageRequest,
    current_user: Utilisateur = Depends(require_role(RoleEnum.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    current = await ensure_can_receive_assistant_message(payload.numero, db)
    return await handle_whatsapp_message(payload.numero, payload.question, current, db)


@router.post("/agent/test-message")
async def api_test_agent_message(
    payload: TestMessageRequest,
    current_user: Utilisateur = Depends(require_role(RoleEnum.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    current = await ensure_can_receive_assistant_message(payload.numero, db)
    return await handle_agent_message(payload.numero, payload.question, current, db)
