"""
AutoCommerce Clinic — API Routes Copilote CRM (Bloc 7)

Routes pour accéder aux fonctionnalités d'assistance CRM sur les fiches patients.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_db
from middleware.clinic_rbac import require_role
from models.database import RoleEnum
from services.copilote_crm import CopiloteCRMService

router = APIRouter(prefix="/copilote-crm", tags=["copilote-crm"])


@router.get("/patient/{patient_id}/summary", summary="Résumer le dossier patient")
async def summarize_patient_file(
    patient_id: int,
    current_user: dict = Depends(require_role(RoleEnum.MEDECIN, RoleEnum.DIRECTRICE, RoleEnum.ADMIN)),
    session: AsyncSession = Depends(get_db),
):
    """
    Résumer le dossier patient : historique, actes, photos, satisfaction.
    """
    try:
        summary = await CopiloteCRMService.summarize_patient_file(session, patient_id)
        if "error" in summary:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=summary["error"]
            )
        return {"status": "success", "data": summary}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors du résumé du dossier : {str(e)}"
        )


@router.get("/patient/{patient_id}/suggest-treatment", summary="Suggérer un traitement")
async def suggest_treatment(
    patient_id: int,
    current_user: dict = Depends(require_role(RoleEnum.MEDECIN, RoleEnum.DIRECTRICE, RoleEnum.ADMIN)),
    session: AsyncSession = Depends(get_db),
):
    """
    Suggérer un traitement basé sur l'historique du patient.
    """
    try:
        suggestions = await CopiloteCRMService.suggest_treatment(session, patient_id)
        if "error" in suggestions:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=suggestions["error"]
            )
        return {"status": "success", "data": suggestions}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la suggestion de traitement : {str(e)}"
        )


@router.get("/at-risk-patients", summary="Détecter les patients à risque")
async def detect_at_risk_patients(
    current_user: dict = Depends(require_role(RoleEnum.MEDECIN, RoleEnum.DIRECTRICE, RoleEnum.ADMIN)),
    session: AsyncSession = Depends(get_db),
):
    """
    Détecter les patients à risque de départ.
    """
    try:
        at_risk = await CopiloteCRMService.detect_at_risk_patients(
            session, current_user["clinic_id"]
        )
        return {"status": "success", "data": at_risk}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la détection des patients à risque : {str(e)}"
        )


@router.get("/patient/{patient_id}/medical-report", summary="Générer un compte rendu médical")
async def generate_medical_report(
    patient_id: int,
    current_user: dict = Depends(require_role(RoleEnum.MEDECIN, RoleEnum.DIRECTRICE, RoleEnum.ADMIN)),
    session: AsyncSession = Depends(get_db),
):
    """
    Générer un compte rendu médical du patient.
    """
    try:
        report = await CopiloteCRMService.generate_medical_report(session, patient_id)
        if "error" in report:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=report["error"]
            )
        return {"status": "success", "data": report}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la génération du rapport : {str(e)}"
        )


@router.get("/patient/{patient_id}/prepare-appointment", summary="Préparer le prochain RDV")
async def prepare_next_appointment(
    patient_id: int,
    current_user: dict = Depends(require_role(RoleEnum.MEDECIN, RoleEnum.DIRECTRICE, RoleEnum.ADMIN)),
    session: AsyncSession = Depends(get_db),
):
    """
    Préparer le prochain rendez-vous du patient.
    """
    try:
        preparation = await CopiloteCRMService.prepare_next_appointment(session, patient_id)
        if "error" in preparation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=preparation["error"]
            )
        return {"status": "success", "data": preparation}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la préparation du RDV : {str(e)}"
        )


@router.get("/patient/{patient_id}/whatsapp-draft", summary="Générer un brouillon WhatsApp")
async def generate_whatsapp_draft(
    patient_id: int,
    message_type: str = "appointment_reminder",
    current_user: dict = Depends(require_role(RoleEnum.MEDECIN, RoleEnum.DIRECTRICE, RoleEnum.ADMIN)),
    session: AsyncSession = Depends(get_db),
):
    """
    Générer un brouillon de message WhatsApp (jamais envoyé sans validation).
    """
    try:
        draft = await CopiloteCRMService.generate_whatsapp_draft(
            session, patient_id, message_type
        )
        if "error" in draft:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=draft["error"]
            )
        return {"status": "success", "data": draft}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la génération du brouillon : {str(e)}"
        )


@router.get("/patient/{patient_id}/email-draft", summary="Générer un brouillon email")
async def generate_email_draft(
    patient_id: int,
    email_type: str = "appointment_reminder",
    current_user: dict = Depends(require_role(RoleEnum.MEDECIN, RoleEnum.DIRECTRICE, RoleEnum.ADMIN)),
    session: AsyncSession = Depends(get_db),
):
    """
    Générer un brouillon d'email (jamais envoyé sans validation).
    """
    try:
        draft = await CopiloteCRMService.generate_email_draft(
            session, patient_id, email_type
        )
        if "error" in draft:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=draft["error"]
            )
        return {"status": "success", "data": draft}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la génération du brouillon : {str(e)}"
        )
