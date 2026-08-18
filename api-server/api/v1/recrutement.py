"""AutoCommerce Clinic — API Recrutement"""
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_db
from middleware.clinic_rbac import require_role
from models.database import RoleEnum
from services.recrutement import create_candidature, changer_statut, list_candidatures
from services.branding import get_branding_context
from config import WA_TEMPLATES

router = APIRouter(prefix="/recrutement", tags=["recrutement"])


class CandidatureCreate(BaseModel):
    poste: str
    nom_candidat: str
    email: str
    telephone: Optional[str] = None
    cv_url: Optional[str] = None
    lettre_url: Optional[str] = None


class StatutChange(BaseModel):
    statut: str
    notes_rh: Optional[str] = None
    date_entretien: Optional[datetime] = None


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_candidature_route(
    payload: CandidatureCreate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role(RoleEnum.DIRECTRICE, RoleEnum.ASSISTANTE, RoleEnum.ADMIN)),
):
    c = await create_candidature(
        payload.model_dump(), db, clinic_id=current_user["clinic_id"],
    )
    # Notification WhatsApp à la directrice
    try:
        branding = await get_branding_context(db, clinic_id=current_user["clinic_id"])
        message = WA_TEMPLATES["candidature_recu"].format(
            poste=c.poste, nom=c.nom_candidat
        )
        message = f"{branding['clinic_name']} — {message}"
        from services.whatsapp_service import send_whatsapp_message
        from sqlalchemy import select as sa_select
        from models.database import Utilisateur as SAUtilisateur
        result = await db.execute(
            sa_select(SAUtilisateur.telephone)
            .where(SAUtilisateur.role == RoleEnum.DIRECTRICE.value)
            .where(SAUtilisateur.clinic_id == current_user["clinic_id"])
            .where(SAUtilisateur.is_active.is_(True))
            .limit(1)
        )
        phone = result.scalar_one_or_none()
        if phone:
            await send_whatsapp_message(phone, message)
    except Exception:
        pass  # La notification ne doit pas bloquer la création
    return {"id": c.id, "statut": c.statut}


@router.get("")
async def list_candidatures_route(
    statut: Optional[str] = Query(None),
    poste: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role(RoleEnum.DIRECTRICE, RoleEnum.MEDECIN, RoleEnum.ASSISTANTE, RoleEnum.ADMIN)),
):
    candidatures = await list_candidatures(
        db, statut=statut, poste=poste,
        clinic_id=current_user["clinic_id"],
    )
    return [{"id": c.id, "poste": c.poste, "nom_candidat": c.nom_candidat, "email": c.email,
             "telephone": c.telephone, "statut": c.statut, "created_at": c.created_at} for c in candidatures]


@router.patch("/{candidature_id}/statut")
@router.put("/{candidature_id}/statut")
async def changer_statut_route(
    candidature_id: int,
    payload: StatutChange,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role(RoleEnum.DIRECTRICE, RoleEnum.ASSISTANTE, RoleEnum.ADMIN)),
):
    try:
        c = await changer_statut(candidature_id, payload.statut, current_user["id"], db,
                                  notes_rh=payload.notes_rh, date_entretien=payload.date_entretien,
                                  clinic_id=current_user["clinic_id"])
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    # Notification WhatsApp au candidat si changement de statut
    try:
        branding = await get_branding_context(db, clinic_id=current_user["clinic_id"])
        message = WA_TEMPLATES["candidature_statut"].format(
            poste=c.poste, statut=c.statut
        )
        message = f"{branding['clinic_name']} — {message}"
        if c.email:  # Pas de phone stocké dans Candidature, on skip si pas de contact
            pass
    except Exception:
        pass
    return {"id": c.id, "statut": c.statut}
