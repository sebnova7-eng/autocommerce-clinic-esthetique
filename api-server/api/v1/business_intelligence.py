"""
AutoCommerce Clinic — API Routes Business Intelligence (Bloc 8)

Routes pour accéder aux analyses et rapports business.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_db
from middleware.clinic_rbac import require_role
from models.database import RoleEnum
from services.business_intelligence import BusinessIntelligenceService

router = APIRouter(prefix="/business-intelligence", tags=["business-intelligence"])


@router.get("/revenue-summary", summary="Résumé des revenus")
async def get_revenue_summary(
    period_days: int = 30,
    current_user: dict = Depends(require_role(RoleEnum.ADMIN, RoleEnum.DIRECTRICE)),
    session: AsyncSession = Depends(get_db),
):
    """
    Obtenir le résumé des revenus : CA total, par médecin, par soin, tendances.
    """
    try:
        summary = await BusinessIntelligenceService.get_revenue_summary(
            session, current_user["clinic_id"], period_days
        )
        return {"status": "success", "data": summary}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors du chargement du résumé des revenus : {str(e)}"
        )


@router.get("/top-practitioners", summary="Médecins les plus rentables")
async def get_top_practitioners(
    period_days: int = 30,
    limit: int = 10,
    current_user: dict = Depends(require_role(RoleEnum.ADMIN, RoleEnum.DIRECTRICE)),
    session: AsyncSession = Depends(get_db),
):
    """
    Obtenir les médecins les plus rentables : CA, nombre de patients, satisfaction.
    """
    try:
        practitioners = await BusinessIntelligenceService.get_top_practitioners(
            session, current_user["clinic_id"], period_days, limit
        )
        return {"status": "success", "data": practitioners}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors du chargement des praticiens : {str(e)}"
        )


@router.get("/top-treatments", summary="Soins les plus performants")
async def get_top_treatments(
    period_days: int = 30,
    limit: int = 10,
    current_user: dict = Depends(require_role(RoleEnum.ADMIN, RoleEnum.DIRECTRICE)),
    session: AsyncSession = Depends(get_db),
):
    """
    Obtenir les soins les plus performants : CA, nombre de patients, satisfaction.
    """
    try:
        treatments = await BusinessIntelligenceService.get_top_treatments(
            session, current_user["clinic_id"], period_days, limit
        )
        return {"status": "success", "data": treatments}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors du chargement des soins : {str(e)}"
        )


@router.get("/top-loyal-patients", summary="Patients les plus fidèles")
async def get_top_loyal_patients(
    limit: int = 20,
    current_user: dict = Depends(require_role(RoleEnum.ADMIN, RoleEnum.DIRECTRICE)),
    session: AsyncSession = Depends(get_db),
):
    """
    Obtenir les patients les plus fidèles : CA, nombre de visites, niveau de fidélité.
    """
    try:
        patients = await BusinessIntelligenceService.get_top_loyal_patients(
            session, current_user["clinic_id"], limit
        )
        return {"status": "success", "data": patients}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors du chargement des patients fidèles : {str(e)}"
        )


@router.get("/underutilized-slots", summary="Créneaux sous-utilisés")
async def get_underutilized_slots(
    period_days: int = 30,
    current_user: dict = Depends(require_role(RoleEnum.ADMIN, RoleEnum.DIRECTRICE)),
    session: AsyncSession = Depends(get_db),
):
    """
    Obtenir les créneaux sous-utilisés : analyse des disponibilités vs réservations.
    """
    try:
        slots = await BusinessIntelligenceService.get_underutilized_slots(
            session, current_user["clinic_id"], period_days
        )
        return {"status": "success", "data": slots}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors du chargement des créneaux : {str(e)}"
        )


@router.get("/revenue-forecast", summary="Prévision des revenus à 30 jours")
async def forecast_revenue_30_days(
    current_user: dict = Depends(require_role(RoleEnum.ADMIN, RoleEnum.DIRECTRICE)),
    session: AsyncSession = Depends(get_db),
):
    """
    Obtenir la prévision des revenus à 30 jours basée sur les RDV planifiés.
    """
    try:
        forecast = await BusinessIntelligenceService.forecast_revenue_30_days(
            session, current_user["clinic_id"]
        )
        return {"status": "success", "data": forecast}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors du chargement de la prévision : {str(e)}"
        )


@router.get("/business-report", summary="Rapport business complet")
async def generate_business_report(
    period_days: int = 30,
    current_user: dict = Depends(require_role(RoleEnum.ADMIN, RoleEnum.DIRECTRICE)),
    session: AsyncSession = Depends(get_db),
):
    """
    Générer un rapport complet pour export PDF/Excel.
    """
    try:
        report = await BusinessIntelligenceService.generate_business_report(
            session, current_user["clinic_id"], period_days
        )
        return {"status": "success", "data": report}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la génération du rapport : {str(e)}"
        )


@router.get("/kpi-dashboard", summary="Tableau de bord KPI")
async def get_kpi_dashboard(
    current_user: dict = Depends(require_role(RoleEnum.ADMIN, RoleEnum.DIRECTRICE)),
    session: AsyncSession = Depends(get_db),
):
    """
    Obtenir le tableau de bord KPI pour la direction.
    """
    try:
        kpis = await BusinessIntelligenceService.get_kpi_dashboard(
            session, current_user["clinic_id"]
        )
        return {"status": "success", "data": kpis}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors du chargement des KPI : {str(e)}"
        )
