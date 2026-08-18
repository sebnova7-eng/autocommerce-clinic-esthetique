"""
AutoCommerce Clinic — API Dossiers Médicaux, Consentements, Photos
"""

from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Request, Response, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from models.database import (
    DossierMedical, Consentement, PhotoClinic,
)
from api.deps import get_db
from middleware.clinic_rbac import require_role
from models.database import RoleEnum

from services.dossier_medical import create_dossier, get_timeline_patient, export_dossier_pdf
from services.consentement import sign_consent
from services.photos_clinic import upload_photo, get_comparaison_avant_apres, delete_photo, get_decrypted_photo
from services.audit_medical import log_access

router = APIRouter(prefix="/patients", tags=["dossiers-medicaux"])


# ── Schémas ────────────────────────────────────────────────

class DossierCreate(BaseModel):
    praticien_id: int
    rdv_id: Optional[int] = None
    acte_id: Optional[int] = None
    date_acte: str  # ISO
    zones_traitees: Optional[dict] = None
    produits_utilises: Optional[dict] = None
    observations: Optional[str] = None
    effets_secondaires: Optional[str] = None
    satisfaction_patient: Optional[int] = Field(None, ge=1, le=5)
    suivi_requis: bool = False
    date_suivi_recommandee: Optional[str] = None
    actes_details: Optional[List[dict]] = None


class ConsentementCreate(BaseModel):
    acte_id: Optional[int] = None
    signature_base64: str
    methode_signature: str = "tactile"
    type_consentement: Optional[str] = Field(
        default=None,
        pattern="^(general|acte_medical|simulation_ia)$",
    )


# ── Dossiers ─────────────────────────────────────────────

@router.post("/{patient_id}/dossiers", response_model=dict)
async def create_patient_dossier(
    patient_id: int,
    data: DossierCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role(RoleEnum.MEDECIN, RoleEnum.ESTHETICIENNE)),
):
    """Crée un dossier médical (vérifie consentement)."""
    try:
        dossier = await create_dossier(
            patient_id=patient_id,
            praticien_id=data.praticien_id,
            rdv_id=data.rdv_id,
            data={
                "acte_id": data.acte_id,
                "date_acte": datetime.fromisoformat(data.date_acte.replace("Z", "+00:00")).replace(tzinfo=None),
                "zones_traitees": data.zones_traitees,
                "produits_utilises": data.produits_utilises,
                "observations": data.observations,
                "effets_secondaires": data.effets_secondaires,
                "satisfaction_patient": data.satisfaction_patient,
                "suivi_requis": data.suivi_requis,
                "date_suivi_recommandee": datetime.strptime(data.date_suivi_recommandee, "%Y-%m-%d").date() if data.date_suivi_recommandee else None,
                "actes_details": data.actes_details,
            },
            db=db,
            clinic_id=current_user["clinic_id"],
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )
        return {"dossier_id": dossier.id, "message": "Dossier créé avec succès"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{patient_id}/dossiers", response_model=List[dict])
async def get_patient_timeline(
    patient_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role(RoleEnum.MEDECIN, RoleEnum.ESTHETICIENNE, RoleEnum.DIRECTRICE)),
):
    """Timeline chronologique des dossiers."""
    return await get_timeline_patient(
        patient_id, db,
        utilisateur_id=current_user["id"],
        ip_address=request.client.host if request.client else None,
        user_role=current_user.get("role"),
        clinic_id=current_user["clinic_id"]
    )


@router.get("/{patient_id}/dossiers/{dossier_id}", response_model=dict)
async def get_dossier_detail(
    patient_id: int,
    dossier_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role(RoleEnum.MEDECIN, RoleEnum.ESTHETICIENNE, RoleEnum.DIRECTRICE)),
):
    """Détail d'un dossier."""
    result = await db.execute(
        select(DossierMedical).where(
            DossierMedical.id == dossier_id,
            DossierMedical.patient_id == patient_id,
            DossierMedical.clinic_id == current_user["clinic_id"],
        )
    )
    dossier = result.scalar_one_or_none()
    if not dossier:
        raise HTTPException(status_code=404, detail="Dossier non trouvé")

    await log_access(
        db=db, utilisateur_id=current_user["id"], patient_id=patient_id,
        action="READ_DOSSIER", resource_type="dossier", resource_id=dossier_id,
        ip_address=request.client.host if request.client else None,
    )

    from services.dossier_medical import decrypt_field
    role = current_user.get("role")
    
    return {
        "id": dossier.id,
        "date_acte": dossier.date_acte.isoformat(),
        "observations": decrypt_field(dossier.observations_enc) if (dossier.observations_enc and role != "directrice") else "[ACCÈS RÉSERVÉ]",
        "zones_traitees": dossier.zones_traitees,
        "produits_utilises": dossier.produits_utilises,
        "effets_secondaires": dossier.effets_secondaires if role != "directrice" else "[ACCÈS RÉSERVÉ]",
        "satisfaction": dossier.satisfaction_patient,
    }


@router.get("/{patient_id}/export-pdf")
async def export_patient_pdf(
    patient_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role(RoleEnum.MEDECIN, RoleEnum.DIRECTRICE)),
):
    """Export PDF complet du dossier patient."""
    await log_access(
        db=db, utilisateur_id=current_user["id"], patient_id=patient_id,
        action="EXPORT_PDF", resource_type="dossier_complet", resource_id=patient_id,
        ip_address=request.client.host if request.client else None,
    )
    from fastapi.responses import Response
    pdf_bytes = await export_dossier_pdf(
        patient_id, db,
        user_role=current_user.get("role"),
        clinic_id=current_user["clinic_id"]
    )
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="dossier_patient_{patient_id}.pdf"'},
    )


# ── Consentements ─────────────────────────────────────────

@router.post("/{patient_id}/consentements", response_model=dict)
async def create_consentement(
    patient_id: int,
    data: ConsentementCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role(RoleEnum.MEDECIN, RoleEnum.ESTHETICIENNE, RoleEnum.DIRECTRICE)),
):
    """Signe un consentement."""
    try:
        consent = await sign_consent(
            patient_id=patient_id,
            acte_id=data.acte_id,
            signature_b64=data.signature_base64,
            method=data.methode_signature,
            ip_address=request.client.host if request.client else None,
            db=db,
            type_consentement=data.type_consentement,
            clinic_id=current_user["clinic_id"],
        )
        return {
            "consentement_id": consent.id,
            "type_consentement": consent.type_consentement,
            "est_valide": consent.est_valide,
            "signe_le": consent.signe_le.isoformat(),
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{patient_id}/consentements", response_model=List[dict])
async def list_consentements(
    patient_id: int,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role(RoleEnum.MEDECIN, RoleEnum.ESTHETICIENNE, RoleEnum.DIRECTRICE)),
):
    """Liste les consentements d'un patient."""
    result = await db.execute(
        select(Consentement)
        .where(
            Consentement.patient_id == patient_id,
            Consentement.clinic_id == current_user["clinic_id"],
        )
        .order_by(Consentement.signe_le.desc())
    )
    consentements = result.scalars().all()
    return [
        {
            "id": c.id,
            "type": c.type_consentement,
            "acte_id": c.acte_id,
            "signe_le": c.signe_le.isoformat(),
            "methode": c.methode_signature,
            "est_valide": c.est_valide,
        }
        for c in consentements
    ]


# ── Photos ─────────────────────────────────────────────────

@router.post("/{patient_id}/photos", response_model=dict)
async def upload_patient_photo(
    patient_id: int,
    request: Request,
    dossier_id: Optional[int] = Query(None),
    type_photo: str = Query(..., pattern="^(avant|apres|progression|complication|autre)$"),
    zone: Optional[str] = Query(None),
    angle: Optional[str] = Query(None),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role(RoleEnum.MEDECIN, RoleEnum.ESTHETICIENNE)),
):
    """Upload une photo médicale."""
    try:
        file_bytes = await file.read()
        photo = await upload_photo(
            patient_id=patient_id,
            dossier_id=dossier_id,
            type_photo=type_photo,
            zone=zone,
            angle=angle,
            file_bytes=file_bytes,
            mime_type=file.content_type or "image/jpeg",
            prise_par_id=current_user["id"],
            db=db,
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
            clinic_id=current_user["clinic_id"],
        )
        return {
            "photo_id": photo.id,
            "url": f"/api/v1/patients/{patient_id}/photos/{photo.id}/view",
            "thumbnail": f"/api/v1/patients/{patient_id}/photos/{photo.id}/view?thumbnail=true",
            "hash": photo.hash_fichier,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{patient_id}/photos", response_model=List[dict])
async def list_photos(
    patient_id: int,
    zone: Optional[str] = Query(None),
    type_photo: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role(RoleEnum.MEDECIN, RoleEnum.ESTHETICIENNE, RoleEnum.DIRECTRICE)),
):
    """Liste les photos d'un patient."""
    from sqlalchemy import and_
    query = select(PhotoClinic).where(
        and_(
            PhotoClinic.patient_id == patient_id,
            PhotoClinic.clinic_id == current_user["clinic_id"],
            ~PhotoClinic.is_deleted,
        )
    )
    if zone:
        query = query.where(PhotoClinic.zone_anatomique == zone)
    if type_photo:
        query = query.where(PhotoClinic.type == type_photo)

    query = query.order_by(PhotoClinic.date_prise.desc())
    result = await db.execute(query)
    photos = result.scalars().all()

    return [
        {
            "id": p.id,
            "type": p.type,
            "zone": p.zone_anatomique,
            "date": p.date_prise.isoformat(),
            "thumbnail": f"/api/v1/patients/{patient_id}/photos/{p.id}/view?thumbnail=true",
            "visible_patient": p.visible_patient,
            "visible_marketing": p.visible_marketing,
        }
        for p in photos
    ]


@router.get("/{patient_id}/photos/avant-apres")
async def get_avant_apres(
    patient_id: int,
    request: Request,
    zone: Optional[str] = Query(None),
    serie_id: Optional[int] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role(RoleEnum.MEDECIN, RoleEnum.ESTHETICIENNE)),
):
    """Photos avant/après pour comparaison."""
    return await get_comparaison_avant_apres(
        patient_id, zone, serie_id, db,
        utilisateur_id=current_user["id"],
        ip_address=request.client.host if request.client else None,
        clinic_id=current_user["clinic_id"],
    )


@router.get("/{patient_id}/photos/{photo_id}/view")
async def view_photo(
    patient_id: int,
    photo_id: int,
    thumbnail: bool = Query(False),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role(RoleEnum.MEDECIN, RoleEnum.ESTHETICIENNE)),
):
    """Déchiffre et retourne une photo médicale (JPEG). Sans cette route,
    le frontend n'a aucun moyen d'afficher les photos avant/après."""
    try:
        content, filename = await get_decrypted_photo(
            photo_id, patient_id, db, thumbnail=thumbnail,
            clinic_id=current_user["clinic_id"],
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    return Response(
        content=content,
        media_type="image/jpeg",
        headers={
            "Content-Disposition": f'inline; filename="{filename}"',
            "Cache-Control": "private, no-store",
        },
    )


@router.delete("/{patient_id}/photos/{photo_id}")
async def soft_delete_photo(
    patient_id: int,
    photo_id: int,
    request: Request,
    raison: str = Query(..., min_length=5),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role(RoleEnum.MEDECIN)),
):
    """Soft delete d'une photo (jamais suppression physique)."""
    try:
        photo = await delete_photo(
            photo_id=photo_id,
            patient_id=patient_id,
            raison=raison,
            deleted_by=current_user["id"],
            db=db,
            clinic_id=current_user["clinic_id"],
            ip_address=request.client.host if request.client else None,
        )
        return {
            "photo_id": photo.id,
            "is_deleted": photo.is_deleted,
            "deleted_at": photo.deleted_at.isoformat() if photo.deleted_at else None,
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
