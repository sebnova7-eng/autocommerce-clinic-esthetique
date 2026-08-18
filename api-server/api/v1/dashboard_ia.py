"""
AutoCommerce Clinic — API Routes Dashboard IA (Bloc 5)

Routes pour accéder au Dashboard IA avec tous les widgets et données agrégées.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_db
from middleware.clinic_rbac import require_role
from models.database import RoleEnum
from services.dashboard_ia import DashboardIAService
from config import get_settings

router = APIRouter(prefix="/dashboard-ia", tags=["dashboard-ia"])


@router.get("/health", summary="Vérification santé dashboard")
async def get_dashboard_health(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_role(
        RoleEnum.DIRECTRICE, RoleEnum.MEDECIN, RoleEnum.ESTHETICIENNE,
        RoleEnum.ASSISTANTE, RoleEnum.ADMIN,
    ))
):
    """Vérifie la santé des sources du dashboard (DB)."""
    from sqlalchemy import text
    try:
        await db.execute(text("SELECT 1"))
        return {"status": "ok", "database": "connected"}
    except Exception as e:
        raise HTTPException(status_code=503, detail={"status": "error", "database": "disconnected", "message": str(e)})


@router.get("/metrics-light", summary="Métriques simplifiées")
async def get_metrics_light(
    current_user: dict = Depends(require_role(
        RoleEnum.DIRECTRICE, RoleEnum.MEDECIN, RoleEnum.ESTHETICIENNE,
        RoleEnum.ASSISTANTE, RoleEnum.ADMIN,
    )),
    session: AsyncSession = Depends(get_db),
):
    """Retourne les métriques clés du jour en format léger."""
    settings = get_settings()
    summary = await DashboardIAService.get_daily_summary(session, current_user["id"], current_user["clinic_id"], settings=settings)
    vip = await DashboardIAService.get_vip_patients(session, current_user["clinic_id"])
    absents = await DashboardIAService.get_absent_patients(session, current_user["clinic_id"])
    
    return {
        "rdv_count": summary.get("rdvs_today_count", 0),
        "ca_jour": summary.get("revenue_today", 0.0),
        "absents": absents.get("total_absent_patients", 0),
        "vip_count": vip.get("total_vip", 0),
        "stock_alerts": summary.get("stock_alerts", 0)
    }


@router.get("/summary", summary="Résumé de la journée")
async def get_daily_summary(
    current_user: dict = Depends(require_role(
        RoleEnum.DIRECTRICE, RoleEnum.MEDECIN, RoleEnum.ESTHETICIENNE,
        RoleEnum.ASSISTANTE, RoleEnum.ADMIN,
    )),
    session: AsyncSession = Depends(get_db),
):
    """
    Obtenir le résumé de la journée : RDV, revenus, patients, alertes.
    """
    try:
        settings = get_settings()
        summary = await DashboardIAService.get_daily_summary(
            session, current_user["id"], current_user["clinic_id"], settings=settings
        )
        return {"status": "success", "data": summary}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors du chargement du résumé : {str(e)}"
        )


@router.get("/absent-patients", summary="Patients absents")
async def get_absent_patients(
    days: int = 30,
    current_user: dict = Depends(require_role(
        RoleEnum.DIRECTRICE, RoleEnum.MEDECIN, RoleEnum.ESTHETICIENNE,
        RoleEnum.ASSISTANTE, RoleEnum.ADMIN,
    )),
    session: AsyncSession = Depends(get_db),
):
    """
    Obtenir la liste des patients absents depuis N jours.
    """
    try:
        data = await DashboardIAService.get_absent_patients(
            session, current_user["clinic_id"], days
        )
        return {"status": "success", "data": data}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors du chargement des patients absents : {str(e)}"
        )


@router.get("/vip-patients", summary="Patients VIP")
async def get_vip_patients(
    current_user: dict = Depends(require_role(
        RoleEnum.DIRECTRICE, RoleEnum.MEDECIN, RoleEnum.ESTHETICIENNE,
        RoleEnum.ASSISTANTE, RoleEnum.ADMIN,
    )),
    session: AsyncSession = Depends(get_db),
):
    """
    Obtenir la liste des patients VIP et GOLD.
    """
    try:
        data = await DashboardIAService.get_vip_patients(
            session, current_user["clinic_id"]
        )
        return {"status": "success", "data": data}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors du chargement des patients VIP : {str(e)}"
        )


@router.get("/ai-recommendations", summary="Recommandations IA")
async def get_ai_recommendations(
    current_user: dict = Depends(require_role(
        RoleEnum.DIRECTRICE, RoleEnum.MEDECIN, RoleEnum.ESTHETICIENNE,
        RoleEnum.ASSISTANTE, RoleEnum.ADMIN,
    )),
    session: AsyncSession = Depends(get_db),
):
    """
    Obtenir les recommandations IA basées sur les données.
    """
    try:
        settings = get_settings()
        data = await DashboardIAService.get_ai_recommendations(
            session, current_user["clinic_id"], settings=settings
        )
        return {"status": "success", "data": data}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors du chargement des recommandations : {str(e)}"
        )


@router.get("/revenue-forecast", summary="Prévision de revenus")
async def get_revenue_forecast(
    days: int = 7,
    current_user: dict = Depends(require_role(
        RoleEnum.DIRECTRICE, RoleEnum.MEDECIN, RoleEnum.ESTHETICIENNE,
        RoleEnum.ASSISTANTE, RoleEnum.ADMIN,
    )),
    session: AsyncSession = Depends(get_db),
):
    """
    Obtenir la prévision de revenus pour les N prochains jours.
    """
    try:
        settings = get_settings()
        data = await DashboardIAService.get_revenue_forecast(
            session, current_user["clinic_id"], days, settings=settings
        )
        return {"status": "success", "data": data}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors du chargement de la prévision : {str(e)}"
        )


@router.get("/cancellation-risk", summary="Risque prédictif d'annulation")
async def get_cancellation_risk(
    horizon_days: int = 30,
    current_user: dict = Depends(require_role(
        RoleEnum.DIRECTRICE, RoleEnum.MEDECIN, RoleEnum.ESTHETICIENNE,
        RoleEnum.ASSISTANTE, RoleEnum.ADMIN,
    )),
    session: AsyncSession = Depends(get_db),
):
    """Retourne les risques calculés depuis les historiques réels de RDV."""
    if horizon_days < 1 or horizon_days > 180:
        raise HTTPException(status_code=400, detail="horizon_days doit être compris entre 1 et 180")
    try:
        data = await DashboardIAService.get_cancellation_risk(
            session, current_user["clinic_id"], horizon_days
        )
        return {"status": "success", "data": data}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors du calcul du risque d'annulation : {str(e)}"
        )


@router.get("/practitioner-performance", summary="Performance des praticiens")
async def get_practitioner_performance(
    current_user: dict = Depends(require_role(
        RoleEnum.DIRECTRICE, RoleEnum.MEDECIN, RoleEnum.ESTHETICIENNE,
        RoleEnum.ASSISTANTE, RoleEnum.ADMIN,
    )),
    session: AsyncSession = Depends(get_db),
):
    """
    Obtenir la performance des praticiens : RDV, revenus, satisfaction.
    """
    try:
        data = await DashboardIAService.get_practitioner_performance(
            session, current_user["clinic_id"]
        )
        return {"status": "success", "data": data}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors du chargement de la performance : {str(e)}"
        )


@router.get("/widgets-config", summary="Configuration des widgets")
async def get_widgets_config(
    current_user: dict = Depends(require_role(
        RoleEnum.DIRECTRICE, RoleEnum.MEDECIN, RoleEnum.ESTHETICIENNE,
        RoleEnum.ASSISTANTE, RoleEnum.ADMIN,
    )),
    session: AsyncSession = Depends(get_db),
):
    """
    Obtenir la configuration des widgets du dashboard.
    """
    try:
        data = await DashboardIAService.get_dashboard_widgets_config(
            session, current_user["id"], current_user["clinic_id"]
        )
        return {"status": "success", "data": data}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors du chargement de la configuration : {str(e)}"
        )


@router.get("/full", summary="Dashboard complet")
async def get_full_dashboard(
    current_user: dict = Depends(require_role(
        RoleEnum.DIRECTRICE, RoleEnum.MEDECIN, RoleEnum.ESTHETICIENNE,
        RoleEnum.ASSISTANTE, RoleEnum.ADMIN,
    )),
    session: AsyncSession = Depends(get_db),
):
    """
    Obtenir le dashboard complet avec toutes les données agrégées.
    """
    try:
        settings = get_settings()
        data = await DashboardIAService.get_full_dashboard(
            session, current_user["id"], current_user["clinic_id"], settings=settings
        )
        return {"status": "success", "data": data}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors du chargement du dashboard : {str(e)}"
        )
