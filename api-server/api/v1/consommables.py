from typing import List, Optional, Literal
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field
from decimal import Decimal

from api.deps import get_db
from middleware.clinic_rbac import require_role
from models.database import RoleEnum
from services.consommables import ConsommableService

router = APIRouter(prefix="/consommables", tags=["consommables"])

# --- Schemas ---
class ConsommableBase(BaseModel):
    nom: str
    categorie: str
    unite: str
    seuil_alerte: Decimal = Decimal("0.00")
    stock_minimum: Decimal = Decimal("0.00")
    prix_unitaire: Decimal = Decimal("0.000")
    fournisseur_id: Optional[int] = None

class ConsommableCreate(ConsommableBase):
    stock_actuel: Decimal = Decimal("0.00")

class ConsommableUpdate(ConsommableBase):
    nom: Optional[str] = None
    categorie: Optional[str] = None
    unite: Optional[str] = None

class ConsommableResponse(ConsommableBase):
    id: int
    stock_actuel: Decimal
    is_active: bool

    class Config:
        from_attributes = True

class MouvementCreate(BaseModel):
    type: Literal["entree", "sortie"]
    quantite: float = Field(..., gt=0)
    motif: Optional[str] = None
    reference: Optional[str] = None

# --- Endpoints ---

@router.get("/list", response_model=List[ConsommableResponse])
async def list_consommables(
    db: AsyncSession = Depends(get_db),
    _ = Depends(require_role(RoleEnum.ADMIN, RoleEnum.DIRECTRICE, RoleEnum.ASSISTANTE, RoleEnum.MEDECIN))
):
    return await ConsommableService.get_all(db)

@router.post("/create", response_model=ConsommableResponse, status_code=status.HTTP_201_CREATED)
async def create_consommable(
    data: ConsommableCreate,
    db: AsyncSession = Depends(get_db),
    _ = Depends(require_role(RoleEnum.ADMIN, RoleEnum.DIRECTRICE))
):
    return await ConsommableService.create(db, data.model_dump())

@router.put("/{consommable_id}", response_model=ConsommableResponse)
async def update_consommable(
    consommable_id: int,
    data: ConsommableUpdate,
    db: AsyncSession = Depends(get_db),
    _ = Depends(require_role(RoleEnum.ADMIN, RoleEnum.DIRECTRICE))
):
    updated = await ConsommableService.update(db, consommable_id, data.model_dump(exclude_unset=True))
    if not updated:
        raise HTTPException(status_code=404, detail="Consommable non trouvé")
    return updated

@router.delete("/{consommable_id}")
async def delete_consommable(
    consommable_id: int,
    db: AsyncSession = Depends(get_db),
    _ = Depends(require_role(RoleEnum.ADMIN, RoleEnum.DIRECTRICE))
):
    success = await ConsommableService.delete(db, consommable_id)
    if not success:
        raise HTTPException(status_code=404, detail="Consommable non trouvé")
    return {"status": "success"}

@router.post("/{consommable_id}/mouvement")
async def add_mouvement(
    consommable_id: int,
    data: MouvementCreate,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(require_role(RoleEnum.ADMIN, RoleEnum.DIRECTRICE, RoleEnum.ASSISTANTE, RoleEnum.MEDECIN))
):
    try:
        mvt = await ConsommableService.add_mouvement(
            db,
            consommable_id,
            data.type,
            data.quantite,
            current_user["id"],
            data.motif,
            data.reference
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    if not mvt:
        raise HTTPException(status_code=404, detail="Consommable non trouvé")
    return {"status": "success", "mouvement_id": mvt.id}

@router.get("/alertes")
async def get_alertes(
    db: AsyncSession = Depends(get_db),
    _ = Depends(require_role(RoleEnum.ADMIN, RoleEnum.DIRECTRICE, RoleEnum.ASSISTANTE))
):
    return await ConsommableService.get_alertes(db)
