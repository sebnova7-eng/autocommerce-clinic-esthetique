"""AutoCommerce Clinic — API Fidélité"""
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_db
from middleware.clinic_rbac import require_role
from models.database import RoleEnum
from services.fidelite import add_points, redeem_points, get_historique, get_overview
from services.branding import get_branding_context
from config import WA_TEMPLATES
from sqlalchemy import select as sa_select
from models.database import Patient as SAPatient

router = APIRouter(prefix="/fidelite", tags=["fidelite"])


class PointsRequest(BaseModel):
    points: int
    motif: str


@router.get("")
async def overview_route(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role(RoleEnum.DIRECTRICE, RoleEnum.ASSISTANTE, RoleEnum.ADMIN)),
):
    return await get_overview(db)


@router.get("/{patient_id}/historique")
async def historique_route(
    patient_id: int,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role(RoleEnum.DIRECTRICE, RoleEnum.ASSISTANTE, RoleEnum.ADMIN)),
):
    historique = await get_historique(patient_id, db)
    return [{"type": h.type, "points": h.points, "solde_apres": h.solde_apres,
             "motif": h.motif, "created_at": h.created_at} for h in historique]


@router.post("/{patient_id}/gagner")
async def gagner_route(
    patient_id: int,
    payload: PointsRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role(RoleEnum.DIRECTRICE, RoleEnum.ASSISTANTE, RoleEnum.ADMIN)),
):
    try:
        tx = await add_points(patient_id, payload.points, payload.motif, db)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

    # Notification WhatsApp fidélité
    try:
        branding = await get_branding_context(db)
        patient_result = await db.execute(sa_select(SAPatient).where(SAPatient.id == patient_id))
        patient_obj = patient_result.scalar_one_or_none()
        if patient_obj and patient_obj.whatsapp_phone and not patient_obj.opted_out:
            from services.whatsapp_service import send_whatsapp_message
            message = WA_TEMPLATES["fidelite_gain"].format(
                points=tx.points, solde=tx.solde_apres, niveau=patient_obj.niveau_fidelite or "Bronze"
            )
            message = f"{branding['clinic_name']} — {message}"
            await send_whatsapp_message(patient_obj.whatsapp_phone, message)
    except Exception:
        pass

    return {"solde_apres": tx.solde_apres}


@router.post("/{patient_id}/depenser")
async def depenser_route(
    patient_id: int,
    payload: PointsRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role(RoleEnum.DIRECTRICE, RoleEnum.ASSISTANTE, RoleEnum.ADMIN)),
):
    try:
        tx = await redeem_points(patient_id, payload.points, payload.motif, db)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return {"solde_apres": tx.solde_apres}
