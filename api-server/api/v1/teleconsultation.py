from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from typing import Optional

from api.deps import get_db, require_role
from models.database import RoleEnum
from services.teleconsultation import TeleconsultationService

router = APIRouter(prefix="/teleconsultation", tags=["teleconsultation"])

class TeleconsultationCreate(BaseModel):
    rdv_id: int

class TeleconsultationComplete(BaseModel):
    duree: Optional[int] = None
    notes: Optional[str] = None

@router.post("/creer")
async def creer_teleconsultation(
    data: TeleconsultationCreate,
    db: AsyncSession = Depends(get_db),
    _ = Depends(require_role([RoleEnum.ADMIN, RoleEnum.DIRECTRICE, RoleEnum.MEDECIN, RoleEnum.ASSISTANTE]))
):
    try:
        tc = await TeleconsultationService.creer_pour_rdv(
            db, data.rdv_id, _["clinic_id"] if isinstance(_, dict) else 0,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    if not tc:
        raise HTTPException(status_code=404, detail="Rendez-vous non trouvé")
    return {
        "id": tc.id,
        "rdv_id": tc.rdv_id,
        "lien_visio": tc.lien_visio,
        "statut": tc.statut
    }

@router.get("/{rdv_id}/lien")
async def get_lien_visio(
    rdv_id: int,
    db: AsyncSession = Depends(get_db),
    _ = Depends(require_role([RoleEnum.ADMIN, RoleEnum.DIRECTRICE, RoleEnum.MEDECIN, RoleEnum.ASSISTANTE]))
):
    tc = await TeleconsultationService.get_by_rdv(
        db, rdv_id, _["clinic_id"] if isinstance(_, dict) else 0,
    )
    if not tc:
        raise HTTPException(status_code=404, detail="Téléconsultation non trouvée pour ce RDV")
    return {
        "id": tc.id,
        "lien_visio": tc.lien_visio,
        "statut": tc.statut
    }

@router.post("/{tc_id}/terminer")
async def terminer_teleconsultation(
    tc_id: int,
    data: TeleconsultationComplete,
    db: AsyncSession = Depends(get_db),
    _ = Depends(require_role([RoleEnum.ADMIN, RoleEnum.DIRECTRICE, RoleEnum.MEDECIN]))
):
    success = await TeleconsultationService.marquer_terminee(
        db, tc_id, data.duree, data.notes,
        clinic_id=_["clinic_id"] if isinstance(_, dict) else 0,
    )
    if not success:
        raise HTTPException(status_code=404, detail="Téléconsultation non trouvée")
    return {"status": "success"}
