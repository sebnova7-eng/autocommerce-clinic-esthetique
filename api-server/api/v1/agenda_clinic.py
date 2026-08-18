"""
AutoCommerce Clinic — API Agenda
"""

from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from models.database import (
    RendezVous, Patient, Utilisateur, ActeMedical, StatutRDV,
)
from api.deps import get_db
from middleware.clinic_rbac import require_role
from models.database import RoleEnum

from services.agenda import get_disponibilites, creer_rdv, annuler_rdv

router = APIRouter(prefix="/agenda", tags=["agenda"])


# ── Schémas ────────────────────────────────────────────────

class RDVCreate(BaseModel):
    patient_id: int
    praticien_id: int
    acte_id: int
    date_heure: str  # ISO datetime
    salle: Optional[str] = Field(None, max_length=50)


class RDVUpdate(BaseModel):
    statut: Optional[str] = None
    notes_pre_acte: Optional[str] = None
    notes_post_acte: Optional[str] = None

    @field_validator("statut")
    @classmethod
    def statut_doit_etre_valide(cls, v):
        if v is not None:
            valeurs = [s.value for s in StatutRDV]
            if v not in valeurs:
                raise ValueError(f"statut invalide, doit être l'un de : {', '.join(valeurs)}")
        return v


class RDVOut(BaseModel):
    id: int
    patient_id: int
    patient_nom: str
    praticien_id: int
    praticien_nom: str
    acte_id: Optional[int]
    acte_nom: Optional[str]
    date_heure_debut: str
    date_heure_fin: Optional[str]
    salle: Optional[str]
    statut: str
    consentement_manquant: bool = False

    class Config:
        from_attributes = True


# ── Routes ─────────────────────────────────────────────────

@router.get("", response_model=List[RDVOut])
async def list_agenda(
    praticien_id: Optional[int] = Query(None),
    date_debut: Optional[str] = Query(None),
    date_fin: Optional[str] = Query(None),
    vue: str = Query("semaine", pattern="^(semaine|jour)$"),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role(RoleEnum.DIRECTRICE, RoleEnum.MEDECIN, RoleEnum.ESTHETICIENNE, RoleEnum.ASSISTANTE, RoleEnum.ADMIN)),
):
    """Liste les RDV (vue semaine ou jour)."""
    query = select(RendezVous, Patient, Utilisateur, ActeMedical).join(
        Patient, RendezVous.patient_id == Patient.id
    ).join(
        Utilisateur, RendezVous.praticien_id == Utilisateur.id
    ).outerjoin(
        ActeMedical, RendezVous.acte_id == ActeMedical.id
    ).where(RendezVous.clinic_id == current_user["clinic_id"])

    if praticien_id:
        query = query.where(RendezVous.praticien_id == praticien_id)

    if date_debut:
        dt_debut = datetime.fromisoformat(date_debut)
        query = query.where(RendezVous.date_heure_debut >= dt_debut)

    if date_fin:
        dt_fin = datetime.fromisoformat(date_fin)
        query = query.where(RendezVous.date_heure_debut <= dt_fin)

    query = query.order_by(RendezVous.date_heure_debut)
    result = await db.execute(query)

    rdvs = []
    for rdv, patient, praticien, acte in result.all():
        from services.consentement import verify_consent
        consent_missing = not await verify_consent(
            rdv.patient_id,
            rdv.acte_id,
            db,
            clinic_id=current_user["clinic_id"],
        )

        rdvs.append(RDVOut(
            id=rdv.id,
            patient_id=rdv.patient_id,
            patient_nom=f"{patient.prenom} {patient.nom}",
            praticien_id=rdv.praticien_id,
            praticien_nom=f"{praticien.prenom} {praticien.nom}",
            acte_id=rdv.acte_id,
            acte_nom=acte.nom if acte else None,
            date_heure_debut=rdv.date_heure_debut.isoformat(),
            date_heure_fin=rdv.date_heure_fin.isoformat() if rdv.date_heure_fin else None,
            salle=rdv.salle,
            statut=rdv.statut,
            consentement_manquant=consent_missing,
        ))

    return rdvs


@router.post("/rdv", response_model=RDVOut)
async def create_rdv(
    data: RDVCreate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role(RoleEnum.DIRECTRICE, RoleEnum.ASSISTANTE, RoleEnum.MEDECIN, RoleEnum.ADMIN)),
):
    """Crée un rendez-vous."""
    try:
        date_heure = datetime.fromisoformat(data.date_heure)
        rdv, consent_missing = await creer_rdv(
            patient_id=data.patient_id,
            praticien_id=data.praticien_id,
            acte_id=data.acte_id,
            date_heure=date_heure,
            salle=data.salle,
            db=db,
            created_by=current_user["id"],
        )

        # Récupérer noms
        patient_r = await db.execute(select(Patient).where(Patient.id == data.patient_id))
        patient = patient_r.scalar_one()
        praticien_r = await db.execute(select(Utilisateur).where(Utilisateur.id == data.praticien_id))
        praticien = praticien_r.scalar_one()
        acte_r = await db.execute(select(ActeMedical).where(ActeMedical.id == data.acte_id))
        acte = acte_r.scalar_one()

        return RDVOut(
            id=rdv.id,
            patient_id=rdv.patient_id,
            patient_nom=f"{patient.prenom} {patient.nom}",
            praticien_id=rdv.praticien_id,
            praticien_nom=f"{praticien.prenom} {praticien.nom}",
            acte_id=rdv.acte_id,
            acte_nom=acte.nom,
            date_heure_debut=rdv.date_heure_debut.isoformat(),
            date_heure_fin=rdv.date_heure_fin.isoformat() if rdv.date_heure_fin else None,
            salle=rdv.salle,
            statut=rdv.statut,
            consentement_manquant=consent_missing,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.patch("/rdv/{rdv_id}/statut")
@router.put("/rdv/{rdv_id}/statut")
async def update_rdv_statut(
    rdv_id: int,
    data: RDVUpdate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role(RoleEnum.DIRECTRICE, RoleEnum.ASSISTANTE, RoleEnum.MEDECIN, RoleEnum.ADMIN)),
):
    """Met à jour le statut d'un RDV."""
    result = await db.execute(select(RendezVous).where(RendezVous.id == rdv_id))
    rdv = result.scalar_one_or_none()
    if not rdv:
        raise HTTPException(status_code=404, detail="RDV non trouvé")

    if data.statut:
        rdv.statut = data.statut
    if data.notes_pre_acte is not None:
        rdv.notes_pre_acte = data.notes_pre_acte
    if data.notes_post_acte is not None:
        rdv.notes_post_acte = data.notes_post_acte

    await db.flush()
    return {"message": "RDV mis à jour"}


@router.delete("/rdv/{rdv_id}")
async def cancel_rdv_route(
    rdv_id: int,
    raison: Optional[str] = Query(None, min_length=3),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role(RoleEnum.DIRECTRICE, RoleEnum.ASSISTANTE, RoleEnum.ADMIN)),
):
    """Annule un RDV."""
    if raison is None:
        raison = "Annulation sans raison spécifiée (via API DELETE)"
    """Annule un RDV."""
    try:
        rdv = await annuler_rdv(rdv_id, raison, db)
        return {"message": "RDV annulé", "rdv_id": rdv.id}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/disponibilites/{praticien_id}")
async def get_dispos(
    praticien_id: int,
    date: str = Query(..., description="YYYY-MM-DD"),
    duree: int = Query(30, ge=15, le=240),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role(RoleEnum.DIRECTRICE, RoleEnum.ASSISTANTE, RoleEnum.MEDECIN, RoleEnum.ADMIN)),
):
    """Créneaux libres d'un praticien pour une date."""
    date_jour = datetime.strptime(date, "%Y-%m-%d").date()
    creneaux = await get_disponibilites(praticien_id, date_jour, duree, db)
    return {"praticien_id": praticien_id, "date": date, "creneaux": creneaux}
