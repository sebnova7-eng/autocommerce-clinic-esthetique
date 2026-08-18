from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from api.deps import get_db, require_role
from models.database import RoleEnum
from services.parrainage import ParrainageService

router = APIRouter(prefix="/parrainage", tags=["parrainage"])

class ParrainageUse(BaseModel):
    code: str
    filleul_id: int

@router.get("/code/{patient_id}")
async def get_code_parrain(
    patient_id: int,
    db: AsyncSession = Depends(get_db),
    _ = Depends(require_role([RoleEnum.ADMIN, RoleEnum.DIRECTRICE, RoleEnum.ASSISTANTE]))
):
    code = await ParrainageService.get_ou_creer_code(db, patient_id)
    return {"code": code}

@router.post("/utiliser")
async def utiliser_code(
    data: ParrainageUse,
    db: AsyncSession = Depends(get_db),
    _ = Depends(require_role([RoleEnum.ADMIN, RoleEnum.DIRECTRICE, RoleEnum.ASSISTANTE]))
):
    success = await ParrainageService.utiliser_code(db, data.code, data.filleul_id)
    if not success:
        raise HTTPException(status_code=400, detail="Code invalide ou déjà utilisé")
    return {"status": "success"}

@router.get("/filleuls/{parrain_id}")
async def get_filleuls(
    parrain_id: int,
    db: AsyncSession = Depends(get_db),
    _ = Depends(require_role([RoleEnum.ADMIN, RoleEnum.DIRECTRICE, RoleEnum.ASSISTANTE]))
):
    filleuls = await ParrainageService.get_filleuls(db, parrain_id)
    return [
        {
            "id": p.id,
            "filleul_id": p.filleul_patient_id,
            "date": p.date_parrainage,
            "recompense_attribuee": p.recompense_attribuee
        }
        for p in filleuls
    ]
