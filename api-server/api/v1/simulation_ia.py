"""
AutoCommerce Clinic — API Simulation IA
Génération de simulations avant/après.
"""

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_db
from middleware.clinic_rbac import require_role
from models.database import RoleEnum
from core.medical_ai_policy import MedicalAIBlocked
from services.simulation_morphing import (
    generer_simulation_ia,
    get_decrypted_simulation
)
from services.consentement import sign_consent

router = APIRouter(prefix="/simulation-ia", tags=["simulation-ia"])

class SimulationRequest(BaseModel):
    zone_anatomique: str = Field(..., min_length=2)
    intensite: int = Field(default=20, ge=0, le=100)


class SimulationIAConsentRequest(BaseModel):
    signature_base64: str
    methode_signature: str = "tactile"


async def _sign_simulation_ia_consent(
    patient_id: int,
    data: SimulationIAConsentRequest,
    request: Request,
    db: AsyncSession,
    clinic_id: int | None = None,
) -> dict:
    """Point commun de signature du consentement simulation IA.

    Correctif Bug #10 : expose explicitement un flux backend dédié à la
    signature tactile du consentement ``simulation_ia``.
    """
    try:
        consent = await sign_consent(
            patient_id=patient_id,
            acte_id=None,
            signature_b64=data.signature_base64,
            method=data.methode_signature,
            ip_address=request.client.host if request.client else None,
            db=db,
            type_consentement="simulation_ia",
            clinic_id=clinic_id,
        )
        return {
            "consentement_id": consent.id,
            "type_consentement": consent.type_consentement,
            "est_valide": consent.est_valide,
            "signe_le": consent.signe_le.isoformat(),
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/patients/{patient_id}/consentement", response_model=dict)
async def create_simulation_ia_consent(
    patient_id: int,
    data: SimulationIAConsentRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role(RoleEnum.MEDECIN, RoleEnum.ESTHETICIENNE, RoleEnum.DIRECTRICE, RoleEnum.ADMIN)),
):
    """Compatibilité historique : signe le consentement simulation IA."""
    return await _sign_simulation_ia_consent(
        patient_id, data, request, db, clinic_id=current_user["clinic_id"]
    )


@router.post("/patients/{patient_id}/consents/simulation-ia", response_model=dict)
async def create_simulation_ia_consent_explicit(
    patient_id: int,
    data: SimulationIAConsentRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role(RoleEnum.MEDECIN, RoleEnum.ESTHETICIENNE, RoleEnum.DIRECTRICE, RoleEnum.ADMIN)),
):
    """Route explicite recommandée par l'audit pour le consentement simulation IA."""
    return await _sign_simulation_ia_consent(
        patient_id, data, request, db, clinic_id=current_user["clinic_id"]
    )


@router.post("/patients/{patient_id}/photos/{photo_id}/simuler", response_model=dict)
async def post_simulation(
    patient_id: int,
    photo_id: int,
    data: SimulationRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role(RoleEnum.MEDECIN, RoleEnum.DIRECTRICE, RoleEnum.ADMIN)),
):
    """Génère une simulation IA pour une photo donnée."""
    try:
        simulation = await generer_simulation_ia(
            patient_id=patient_id,
            photo_source_id=photo_id,
            zone=data.zone_anatomique,
            intensite=data.intensite,
            genere_par_id=current_user["id"],
            db=db,
            clinic_id=current_user["clinic_id"],
        )
        return {
            "simulation_id": simulation.id,
            "url_resultat": f"/api/v1/simulation-ia/patients/{patient_id}/simulations/{simulation.id}/view",
            "created_at": simulation.created_at.isoformat()
        }
    except MedicalAIBlocked as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/patients/{patient_id}/simulations/{simulation_id}/view")
async def view_simulation(
    patient_id: int,
    simulation_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role(RoleEnum.MEDECIN, RoleEnum.DIRECTRICE, RoleEnum.ASSISTANTE, RoleEnum.ADMIN)),
):
    """Affiche l'image déchiffrée de la simulation."""
    try:
        img_bytes, filename = await get_decrypted_simulation(
            simulation_id=simulation_id,
            patient_id=patient_id,
            db=db,
            utilisateur_id=current_user["id"],
            clinic_id=current_user["clinic_id"],
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )
        return Response(
            content=img_bytes,
            media_type="image/jpeg",
            headers={"Content-Disposition": f"inline; filename={filename}"}
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
