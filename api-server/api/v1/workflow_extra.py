"""Routes Workflow Engine supplémentaires : preview, decide, approve."""

from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_db, require_role
from config import get_settings
from models.database import RoleEnum
from services.workflow_engine import WorkflowEngineService

router = APIRouter()


class DecidePayload(BaseModel):
    event_type: str
    event_data: Dict[str, Any] = Field(default_factory=dict)


class ApprovePayload(BaseModel):
    action_id: int
    workflow_id: int


@router.post("/decide")
async def decide(
    payload: DecidePayload,
    current_user: dict = Depends(require_role(RoleEnum.ADMIN, RoleEnum.MEDECIN, RoleEnum.DIRECTRICE)),
    db: AsyncSession = Depends(get_db),
):
    clinic_id = current_user.get("clinic_id") if current_user else None
    if clinic_id is None:
        raise HTTPException(status_code=403, detail="Contexte clinique absent")
    workflows = await WorkflowEngineService.get_active_workflows(
        db, clinic_id=clinic_id)
    settings = get_settings()
    decision = await WorkflowEngineService.decide_next_branch(
        db, event_type=payload.event_type, event_data=payload.event_data,
        available_workflows=list(workflows),
        settings=settings,
    )
    return decision


@router.post("/executions/{execution_id}/approve-action")
async def approve(
    execution_id: int, payload: ApprovePayload,
    current_user=Depends(require_role(RoleEnum.ADMIN, RoleEnum.MEDECIN, RoleEnum.DIRECTRICE)),
    db: AsyncSession = Depends(get_db),
):
    """Approuve un brouillon d'action (humain-dans-la-boucle requis)."""
    clinic_id = current_user.get("clinic_id")
    if clinic_id is None:
        raise HTTPException(status_code=403, detail="Contexte clinique absent")
    action = await WorkflowEngineService.approve_drafted_action(
        db, execution_id=execution_id,
        action_id=payload.action_id, clinic_id=clinic_id,
        workflow_id=payload.workflow_id,
    )
    return {
        "id": action.id,
        "action_type": action.action_type,
        "status": action.status,
        "result": action.result,
    }
