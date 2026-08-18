"""AutoCommerce Clinic — API Commissions"""
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_db
from middleware.clinic_rbac import require_role
from models.database import RoleEnum, Utilisateur
from services.commissions import valider_commission, marquer_payee, list_commissions, total_du_par_commercial

router = APIRouter(prefix="/commissions", tags=["commissions"])


class PaiementCommissionRequest(BaseModel):
    date_paiement: date


async def _noms_utilisateurs(db: AsyncSession, ids: set[int]) -> dict[int, str]:
    ids = {i for i in ids if i}
    if not ids:
        return {}
    result = await db.execute(select(Utilisateur).where(Utilisateur.id.in_(ids)))
    return {u.id: f"{u.prenom} {u.nom}" for u in result.scalars().all()}


@router.get("")
async def list_commissions_route(
    periode_mois: date | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role(RoleEnum.DIRECTRICE, RoleEnum.COMMERCIAL, RoleEnum.ADMIN)),
):
    commissions = await list_commissions(current_user, db, periode_mois=periode_mois)
    noms = await _noms_utilisateurs(
        db,
        {c.commercial_id for c in commissions}
        | {c.validee_par_id for c in commissions}
        | {c.validee_par_id_2 for c in commissions},
    )
    return [
        {
            "id": c.id,
            "commercial_id": c.commercial_id,
            "commercial_nom": noms.get(c.commercial_id, ""),
            "patient_id": c.patient_id,
            "montant_ca": c.montant_ca,
            "montant": c.montant_commission,
            "statut": c.statut,
            "periode_mois": c.periode_mois,
            "date_creation": c.created_at,
            "validateur_1_id": c.validee_par_id,
            "validateur_1_nom": noms.get(c.validee_par_id) if c.validee_par_id else None,
            "validateur_2_id": c.validee_par_id_2,
            "validateur_2_nom": noms.get(c.validee_par_id_2) if c.validee_par_id_2 else None,
        }
        for c in commissions
    ]


@router.get("/du/{commercial_id}")
async def total_du_route(
    commercial_id: int,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role(RoleEnum.DIRECTRICE, RoleEnum.ADMIN)),
):
    return {"commercial_id": commercial_id, "total_du": await total_du_par_commercial(commercial_id, db)}


@router.post("/{commission_id}/valider")
@router.patch("/{commission_id}/valider")
async def valider_route(
    commission_id: int,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role(RoleEnum.DIRECTRICE, RoleEnum.ADMIN)),
):
    try:
        commission = await valider_commission(commission_id, current_user["id"], db)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return {"id": commission.id, "statut": commission.statut}


@router.post("/{commission_id}/payer")
async def payer_route(
    commission_id: int,
    payload: PaiementCommissionRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role(RoleEnum.DIRECTRICE, RoleEnum.ADMIN)),
):
    try:
        commission = await marquer_payee(commission_id, payload.date_paiement, db)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return {"id": commission.id, "statut": commission.statut}
