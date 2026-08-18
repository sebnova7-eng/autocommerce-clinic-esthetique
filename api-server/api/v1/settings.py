"""AutoCommerce Clinic — API Settings (branding) & réservation publique"""
from datetime import datetime
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File, status, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_db, limiter
from middleware.clinic_rbac import require_role
from models.database import RoleEnum, Utilisateur, ActeMedical
from services.agenda import get_disponibilites
from services.branding import get_branding, update_branding, save_logo
from services.booking_requests import submit_booking_request
from config import get_settings

router = APIRouter(tags=["private-settings"])
public_router = APIRouter(tags=["public-gateway"])


def _public_clinic_id() -> int:
    settings = get_settings()
    if settings.env == "production" and not settings.public_routes_enabled:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Routes publiques désactivées pour ce déploiement",
        )
    clinic_id = settings.public_clinic_id
    if not isinstance(clinic_id, int) or clinic_id <= 0:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Tenant public non configuré",
        )
    return clinic_id


class ContenuLanding(BaseModel):
    titre: Optional[str] = None
    sous_titre: Optional[str] = None
    services_mis_en_avant: Optional[list[str]] = None
    adresse: Optional[str] = None
    telephone: Optional[str] = None
    horaires: Optional[str] = None


class BrandingUpdate(BaseModel):
    nom_clinique: Optional[str] = None
    couleur_primaire: Optional[str] = None
    couleur_secondaire: Optional[str] = None
    contenu_landing: Optional[ContenuLanding] = None


class ReservationPublique(BaseModel):
    nom: str
    prenom: str
    telephone: str
    email: Optional[str] = None
    praticien_id: Optional[int] = None
    specialite: Optional[str] = None
    acte_id: int
    date_heure: datetime


# ── Branding ───────────────────────────────────────────────

@router.get("/settings/branding")
async def get_branding_route(db: AsyncSession = Depends(get_db)):
    """Public — lu par la landing page avec tenant explicitement configuré."""
    return await get_branding(db, clinic_id=_public_clinic_id())


@router.patch("/settings/branding")
async def update_branding_route(
    payload: BrandingUpdate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role(RoleEnum.DIRECTRICE, RoleEnum.ADMIN)),
):
    data = payload.model_dump(exclude_none=True)
    return await update_branding(
        data, db, clinic_id=current_user["clinic_id"],
    )


@router.post("/settings/branding/logo")
async def upload_logo_route(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role(RoleEnum.DIRECTRICE, RoleEnum.ADMIN)),
):
    file_bytes = await file.read()
    try:
        logo_url = save_logo(
            file_bytes, file.content_type,
            clinic_id=current_user["clinic_id"],
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    updated = await update_branding(
        {"logo_url": logo_url}, db,
        clinic_id=current_user["clinic_id"],
    )
    return {"logo_url": updated["logo_url"]}


# ── Gestion des Actes (Admin) ──────────────────────────────

class ActeCreate(BaseModel):
    nom: str
    categorie: str
    duree_minutes: int = 30
    prix_base: Decimal = Decimal("0.000")
    description: Optional[str] = None
    is_active: bool = True

@router.get("/settings/actes")
async def list_actes_admin_route(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role(RoleEnum.DIRECTRICE, RoleEnum.ADMIN)),
):
    result = await db.execute(select(ActeMedical)
        .where(ActeMedical.clinic_id == current_user["clinic_id"])
        .order_by(ActeMedical.nom))
    return result.scalars().all()

@router.post("/settings/actes", status_code=status.HTTP_201_CREATED)
async def create_acte_route(
    payload: ActeCreate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role(RoleEnum.DIRECTRICE, RoleEnum.ADMIN)),
):
    acte = ActeMedical(
        **payload.model_dump(), clinic_id=current_user["clinic_id"],
    )
    db.add(acte)
    await db.flush()
    return acte

@router.patch("/settings/actes/{acte_id}")
async def update_acte_route(
    acte_id: int,
    payload: ActeCreate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role(RoleEnum.DIRECTRICE, RoleEnum.ADMIN)),
):
    result = await db.execute(select(ActeMedical).where(
        ActeMedical.id == acte_id,
        ActeMedical.clinic_id == current_user["clinic_id"],
    ))
    acte = result.scalar_one_or_none()
    if not acte:
        raise HTTPException(status_code=404, detail="Acte non trouvé")
    
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(acte, field, value)
    
    await db.flush()
    return acte

# ── Réservation publique ───────────────────────────────────

@public_router.get("/praticiens")
async def public_praticiens_route(db: AsyncSession = Depends(get_db)):
    """Liste publique des praticiens réservable depuis la landing page."""
    clinic_id = _public_clinic_id()
    result = await db.execute(
        select(Utilisateur)
        .where(Utilisateur.clinic_id == clinic_id)
        .where(Utilisateur.is_active)
        .where(Utilisateur.role.in_([RoleEnum.MEDECIN.value, RoleEnum.ESTHETICIENNE.value]))
        .order_by(Utilisateur.prenom, Utilisateur.nom)
    )
    praticiens = result.scalars().all()
    return [
        {
            "id": praticien.id,
            "nom": praticien.nom,
            "prenom": praticien.prenom,
            "nom_complet": f"{praticien.prenom} {praticien.nom}",
            "specialite": praticien.specialite,
            "agenda_color": praticien.agenda_color,
        }
        for praticien in praticiens
    ]


@public_router.get("/actes")
async def public_actes_route(db: AsyncSession = Depends(get_db)):
    """Catalogue public des actes activés."""
    clinic_id = _public_clinic_id()
    result = await db.execute(
        select(ActeMedical)
        .where(ActeMedical.clinic_id == clinic_id)
        .where(ActeMedical.is_active)
        .order_by(ActeMedical.nom)
    )
    actes = result.scalars().all()
    return [
        {
            "id": acte.id,
            "nom": acte.nom,
            "categorie": acte.categorie,
            "duree_minutes": acte.duree_minutes,
            "description": acte.description,
            "prix_base": float(acte.prix_base) if acte.prix_base is not None else None,
        }
        for acte in actes
    ]


@public_router.get("/disponibilites/{praticien_id}")
async def public_disponibilites_route(
    praticien_id: int,
    date: Optional[str] = Query(None, description="YYYY-MM-DD"),
    acte_id: Optional[int] = Query(None),
    duree: Optional[int] = Query(None, ge=15, le=240),
    db: AsyncSession = Depends(get_db),
):
    """Créneaux libres publics d'un praticien pour un jour donné."""
    clinic_id = _public_clinic_id()
    praticien_result = await db.execute(
        select(Utilisateur)
        .where(Utilisateur.id == praticien_id)
        .where(Utilisateur.clinic_id == clinic_id)
        .where(Utilisateur.is_active)
        .where(Utilisateur.role.in_([RoleEnum.MEDECIN.value, RoleEnum.ESTHETICIENNE.value]))
    )
    praticien = praticien_result.scalar_one_or_none()
    if not praticien:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Praticien non trouvé")

    if date:
        try:
            date_jour = datetime.strptime(date, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Date invalide (format YYYY-MM-DD)")
    else:
        date_jour = datetime.utcnow().date()

    duree_minutes = duree or 30
    if acte_id is not None:
        acte_result = await db.execute(
            select(ActeMedical)
            .where(ActeMedical.id == acte_id)
            .where(ActeMedical.clinic_id == clinic_id)
            .where(ActeMedical.is_active)
        )
        acte = acte_result.scalar_one_or_none()
        if not acte:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Acte non trouvé")
        duree_minutes = acte.duree_minutes

    creneaux = await get_disponibilites(
        praticien_id, date_jour, duree_minutes, db, clinic_id=clinic_id
    )

    if date_jour == datetime.utcnow().date():
        now = datetime.utcnow()
        creneaux = [
            creneau for creneau in creneaux
            if datetime.fromisoformat(creneau["datetime"]) >= now
        ]

    return {
        "praticien_id": praticien_id,
        "date": date_jour.isoformat(),
        "duree_minutes": duree_minutes,
        "creneaux": creneaux,
    }


@public_router.post("/reservation", status_code=status.HTTP_202_ACCEPTED)
@limiter.limit("5/minute")
async def reservation_publique_route(
    request: Request,
    payload: ReservationPublique,
    db: AsyncSession = Depends(get_db),
):
    """Public — crée une BookingRequest, jamais un Appointment direct.

    La validation par un utilisateur du Private Clinical Core est obligatoire
    avant toute création de patient clinique ou de rendez-vous interne.
    """
    try:
        result = await submit_booking_request(
            payload.model_dump(), db, clinic_id=_public_clinic_id()
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return result
