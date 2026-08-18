"""Routes BI supplémentaires : insights LLM (Bloc 8 v2)."""

from __future__ import annotations


from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_db
from config import get_settings
from middleware.clinic_rbac import require_role
from models.database import RoleEnum
from services.business_intelligence import BusinessIntelligenceService

router = APIRouter()


class LLMBIPayload(BaseModel):
    # Compatibilité de payload uniquement ; ce champ est ignoré côté serveur.
    clinic_id: int | None = None
    period_days: int = Field(default=30, ge=1, le=365)


@router.post("/insights")
async def bi_insights(
    payload: LLMBIPayload,
    current_user: dict = Depends(require_role(RoleEnum.ADMIN, RoleEnum.DIRECTRICE)),
    db: AsyncSession = Depends(get_db),
):
    settings = get_settings()
    return await BusinessIntelligenceService.get_llm_insights(
        db, clinic_id=current_user["clinic_id"], period_days=payload.period_days,
        settings=settings,
    )
