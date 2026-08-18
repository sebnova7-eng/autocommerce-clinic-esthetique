"""
AutoCommerce Clinic — API Routes Workflow Engine (Bloc 6)

Routes pour gérer et exécuter les workflows automatisés.
"""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from api.deps import get_db
from middleware.clinic_rbac import require_role
from models.database import RoleEnum
from models.workflow_engine import Workflow, WorkflowStatus
from services.workflow_engine import WorkflowEngineService

router = APIRouter(prefix="/workflows", tags=["workflows"])


# ═══════════════════════════════════════════════════════════
# Pydantic Models
# ═══════════════════════════════════════════════════════════

class WorkflowCreate(BaseModel):
    nom: str
    description: Optional[str] = None
    trigger_type: str
    trigger_config: Optional[dict] = None
    conditions: Optional[dict] = None
    actions: list
    cron_expression: Optional[str] = None


class WorkflowUpdate(BaseModel):
    nom: Optional[str] = None
    description: Optional[str] = None
    enabled: Optional[bool] = None
    status: Optional[str] = None
    actions: Optional[list] = None


class WorkflowExecutionResponse(BaseModel):
    id: int
    workflow_id: int
    status: str
    trigger_reason: str
    result: Optional[dict] = None
    created_at: str


# ═══════════════════════════════════════════════════════════
# Routes
# ═══════════════════════════════════════════════════════════

@router.get("/", summary="Lister les workflows")
async def list_workflows(
    status_filter: Optional[str] = None,
    current_user: dict = Depends(require_role(RoleEnum.DIRECTRICE, RoleEnum.ADMIN)),
    session: AsyncSession = Depends(get_db),
):
    """
    Lister tous les workflows de la clinique.
    """
    try:
        stmt = select(Workflow).where(Workflow.clinic_id == current_user["clinic_id"])
        
        if status_filter:
            stmt = stmt.where(Workflow.status == status_filter)
        
        workflows = (await session.execute(stmt)).scalars().all()
        
        return {
            "status": "success",
            "data": [
                {
                    "id": w.id,
                    "nom": w.nom,
                    "description": w.description,
                    "trigger_type": w.trigger_type,
                    "enabled": w.enabled,
                    "status": w.status,
                    "created_at": w.created_at.isoformat(),
                }
                for w in workflows
            ]
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors du chargement des workflows : {str(e)}"
        )


@router.post("/", summary="Créer un workflow")
async def create_workflow(
    workflow_data: WorkflowCreate,
    current_user: dict = Depends(require_role(RoleEnum.DIRECTRICE, RoleEnum.ADMIN)),
    session: AsyncSession = Depends(get_db),
):
    """
    Créer un nouveau workflow.
    """
    try:
        workflow = Workflow(
            clinic_id=current_user["clinic_id"],
            nom=workflow_data.nom,
            description=workflow_data.description,
            trigger_type=workflow_data.trigger_type,
            trigger_config=workflow_data.trigger_config,
            conditions=workflow_data.conditions,
            actions=workflow_data.actions,
            cron_expression=workflow_data.cron_expression,
            created_by=current_user["id"],
            status=WorkflowStatus.DRAFT.value,
        )
        session.add(workflow)
        await session.commit()
        
        return {
            "status": "success",
            "message": "Workflow créé avec succès",
            "data": {
                "id": workflow.id,
                "nom": workflow.nom,
            }
        }
    except Exception as e:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la création du workflow : {str(e)}"
        )


@router.get("/{workflow_id}", summary="Obtenir un workflow")
async def get_workflow(
    workflow_id: int,
    current_user: dict = Depends(require_role(RoleEnum.DIRECTRICE, RoleEnum.ADMIN)),
    session: AsyncSession = Depends(get_db),
):
    """
    Obtenir les détails d'un workflow.
    """
    try:
        stmt = select(Workflow).where(
            and_(
                Workflow.id == workflow_id,
                Workflow.clinic_id == current_user["clinic_id"]
            )
        )
        workflow = (await session.execute(stmt)).scalar_one_or_none()
        
        if not workflow:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Workflow non trouvé"
            )
        
        return {
            "status": "success",
            "data": {
                "id": workflow.id,
                "nom": workflow.nom,
                "description": workflow.description,
                "trigger_type": workflow.trigger_type,
                "trigger_config": workflow.trigger_config,
                "conditions": workflow.conditions,
                "actions": workflow.actions,
                "enabled": workflow.enabled,
                "status": workflow.status,
                "created_at": workflow.created_at.isoformat(),
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors du chargement du workflow : {str(e)}"
        )


@router.put("/{workflow_id}", summary="Mettre à jour un workflow")
async def update_workflow(
    workflow_id: int,
    workflow_data: WorkflowUpdate,
    current_user: dict = Depends(require_role(RoleEnum.DIRECTRICE, RoleEnum.ADMIN)),
    session: AsyncSession = Depends(get_db),
):
    """
    Mettre à jour un workflow.
    """
    try:
        stmt = select(Workflow).where(
            and_(
                Workflow.id == workflow_id,
                Workflow.clinic_id == current_user["clinic_id"]
            )
        )
        workflow = (await session.execute(stmt)).scalar_one_or_none()
        
        if not workflow:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Workflow non trouvé"
            )
        
        # Mettre à jour les champs
        if workflow_data.nom is not None:
            workflow.nom = workflow_data.nom
        if workflow_data.description is not None:
            workflow.description = workflow_data.description
        if workflow_data.enabled is not None:
            workflow.enabled = workflow_data.enabled
        if workflow_data.status is not None:
            workflow.status = workflow_data.status
        if workflow_data.actions is not None:
            workflow.actions = workflow_data.actions
        
        await session.commit()
        
        return {
            "status": "success",
            "message": "Workflow mis à jour avec succès",
            "data": {"id": workflow.id}
        }
    except HTTPException:
        raise
    except Exception as e:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la mise à jour du workflow : {str(e)}"
        )


@router.delete("/{workflow_id}", summary="Supprimer un workflow")
async def delete_workflow(
    workflow_id: int,
    current_user: dict = Depends(require_role(RoleEnum.DIRECTRICE, RoleEnum.ADMIN)),
    session: AsyncSession = Depends(get_db),
):
    """
    Supprimer un workflow.
    """
    try:
        stmt = select(Workflow).where(
            and_(
                Workflow.id == workflow_id,
                Workflow.clinic_id == current_user["clinic_id"]
            )
        )
        workflow = (await session.execute(stmt)).scalar_one_or_none()
        
        if not workflow:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Workflow non trouvé"
            )
        
        await session.delete(workflow)
        await session.commit()
        
        return {"status": "success", "message": "Workflow supprimé avec succès"}
    except HTTPException:
        raise
    except Exception as e:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la suppression du workflow : {str(e)}"
        )


@router.post("/{workflow_id}/execute", summary="Exécuter un workflow")
async def execute_workflow(
    workflow_id: int,
    patient_id: Optional[int] = None,
    current_user: dict = Depends(require_role(RoleEnum.DIRECTRICE, RoleEnum.ADMIN)),
    session: AsyncSession = Depends(get_db),
):
    """
    Exécuter manuellement un workflow.
    """
    try:
        stmt = select(Workflow).where(
            and_(
                Workflow.id == workflow_id,
                Workflow.clinic_id == current_user["clinic_id"]
            )
        )
        workflow = (await session.execute(stmt)).scalar_one_or_none()
        
        if not workflow:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Workflow non trouvé"
            )
        
        execution = await WorkflowEngineService.execute_workflow(
            session, workflow, current_user["clinic_id"], patient_id
        )
        await session.commit()
        
        return {
            "status": "success",
            "message": "Workflow exécuté avec succès",
            "data": {
                "execution_id": execution.id,
                "status": execution.status,
                "result": execution.result,
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de l'exécution du workflow : {str(e)}"
        )


@router.get("/{workflow_id}/executions", summary="Historique d'exécution")
async def get_workflow_executions(
    workflow_id: int,
    limit: int = 50,
    current_user: dict = Depends(require_role(RoleEnum.DIRECTRICE, RoleEnum.ADMIN)),
    session: AsyncSession = Depends(get_db),
):
    """
    Obtenir l'historique d'exécution d'un workflow.
    """
    try:
        # Vérifier que le workflow appartient à la clinique
        stmt = select(Workflow).where(
            and_(
                Workflow.id == workflow_id,
                Workflow.clinic_id == current_user["clinic_id"]
            )
        )
        workflow = (await session.execute(stmt)).scalar_one_or_none()
        
        if not workflow:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Workflow non trouvé"
            )
        
        executions = await WorkflowEngineService.get_workflow_execution_history(
            session, workflow_id, limit
        )
        
        return {
            "status": "success",
            "data": [
                {
                    "id": e.id,
                    "status": e.status,
                    "trigger_reason": e.trigger_reason,
                    "result": e.result,
                    "created_at": e.created_at.isoformat(),
                }
                for e in executions
            ]
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors du chargement de l'historique : {str(e)}"
        )


@router.get("/statistics/summary", summary="Statistiques des workflows")
async def get_workflow_statistics(
    days: int = 30,
    current_user: dict = Depends(require_role(RoleEnum.DIRECTRICE, RoleEnum.ADMIN)),
    session: AsyncSession = Depends(get_db),
):
    """
    Obtenir les statistiques des workflows.
    """
    try:
        stats = await WorkflowEngineService.get_workflow_statistics(
            session, current_user["clinic_id"], days
        )
        
        return {"status": "success", "data": stats}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors du chargement des statistiques : {str(e)}"
        )
