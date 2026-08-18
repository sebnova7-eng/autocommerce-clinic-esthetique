from typing import List, Optional
from fastapi import APIRouter, Depends, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime

from api.deps import get_db
from middleware.clinic_rbac import require_role
from models.database import RoleEnum, LaboratoirePartenaire, VisiteDelegue

router = APIRouter(prefix="/delegues", tags=["delegues"])

class LaboCreate(BaseModel):
    nom: str
    contact_nom: Optional[str] = None
    telephone: Optional[str] = None
    email: Optional[str] = None
    adresse: Optional[str] = None

class DelegueCreate(BaseModel):
    labo_id: int
    nom: str
    prenom: str
    telephone: Optional[str] = None
    email: Optional[str] = None

class VisiteCreate(BaseModel):
    delegue_id: int
    medecin_id: Optional[int] = None
    date_visite: datetime
    objet: str
    compte_rendu: Optional[str] = None
    echantillons_recus: Optional[dict] = None

@router.get("/labos", response_model=List[dict])
async def list_labos(db: AsyncSession = Depends(get_db), current_user=Depends(require_role(RoleEnum.ADMIN, RoleEnum.DIRECTRICE, RoleEnum.MEDECIN))):
    result = await db.execute(select(LaboratoirePartenaire).where(LaboratoirePartenaire.clinic_id == current_user["clinic_id"]))
    labos = result.scalars().all()
    return [{"id": labo.id, "nom": labo.nom, "contact": labo.contact_nom} for labo in labos]

@router.post("/labos", status_code=status.HTTP_201_CREATED)
async def create_labo(payload: LaboCreate, db: AsyncSession = Depends(get_db), current_user=Depends(require_role(RoleEnum.ADMIN, RoleEnum.DIRECTRICE))):
    labo = LaboratoirePartenaire(**payload.model_dump(), clinic_id=current_user["clinic_id"])
    db.add(labo)
    await db.commit()
    await db.refresh(labo)
    return labo

@router.get("/visites", response_model=List[dict])
async def list_visites(db: AsyncSession = Depends(get_db), current_user=Depends(require_role(RoleEnum.ADMIN, RoleEnum.DIRECTRICE, RoleEnum.MEDECIN))):
    from sqlalchemy.orm import joinedload
    result = await db.execute(
        select(VisiteDelegue)
        .options(joinedload(VisiteDelegue.delegue))
        .where(VisiteDelegue.clinic_id == current_user["clinic_id"])
        .order_by(VisiteDelegue.date_visite.desc())
    )
    visites = result.scalars().all()
    return [{
        "id": v.id,
        "date": v.date_visite,
        "delegue": f"{v.delegue.prenom} {v.delegue.nom}",
        "objet": v.objet,
        "echantillons": v.echantillons_recus
    } for v in visites]

@router.post("/visites", status_code=status.HTTP_201_CREATED)
async def create_visite(payload: VisiteCreate, db: AsyncSession = Depends(get_db), current_user=Depends(require_role(RoleEnum.ADMIN, RoleEnum.DIRECTRICE, RoleEnum.MEDECIN))):
    visite = VisiteDelegue(**payload.model_dump(), clinic_id=current_user["clinic_id"])
    db.add(visite)
    await db.commit()
    await db.refresh(visite)
    return visite
