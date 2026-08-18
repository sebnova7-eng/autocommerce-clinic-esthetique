"""Routes privées de revue des demandes de réservation publiques."""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_db
from middleware.clinic_rbac import require_role
from models.database import BookingRequest, RoleEnum
from services.booking_requests import approve_booking_request, reject_booking_request

router = APIRouter(prefix="/booking-requests", tags=["booking-requests"])


class BookingRequestReject(BaseModel):
    notes: Optional[str] = Field(default=None, max_length=500)


@router.get("")
async def list_booking_requests(
    statut: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role(RoleEnum.DIRECTRICE, RoleEnum.ASSISTANTE, RoleEnum.ADMIN)),
):
    query = select(BookingRequest).where(BookingRequest.clinic_id == current_user["clinic_id"])
    if statut:
        query = query.where(BookingRequest.statut == statut)
    query = query.order_by(BookingRequest.created_at.desc())
    result = await db.execute(query)
    return result.scalars().all()


@router.post("/{booking_request_id}/approve")
async def approve_booking_request_route(
    booking_request_id: int,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role(RoleEnum.DIRECTRICE, RoleEnum.ASSISTANTE, RoleEnum.ADMIN)),
):
    try:
        return await approve_booking_request(
            booking_request_id,
            db,
            clinic_id=current_user["clinic_id"],
            reviewer_id=current_user["id"],
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.post("/{booking_request_id}/reject")
async def reject_booking_request_route(
    booking_request_id: int,
    payload: BookingRequestReject,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role(RoleEnum.DIRECTRICE, RoleEnum.ASSISTANTE, RoleEnum.ADMIN)),
):
    try:
        return await reject_booking_request(
            booking_request_id,
            db,
            clinic_id=current_user["clinic_id"],
            reviewer_id=current_user["id"],
            notes=payload.notes,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
