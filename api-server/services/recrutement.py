"""AutoCommerce Clinic — Service Recrutement"""
from datetime import datetime
from typing import Optional

from sqlalchemy import select

from models.database import Candidature, StatutCandidature

TRANSITIONS_VALIDES = {
    StatutCandidature.RECU.value: {StatutCandidature.EN_ETUDE.value, StatutCandidature.REFUSE.value},
    StatutCandidature.EN_ETUDE.value: {StatutCandidature.ENTRETIEN.value, StatutCandidature.REFUSE.value},
    StatutCandidature.ENTRETIEN.value: {StatutCandidature.ACCEPTE.value, StatutCandidature.REFUSE.value},
    StatutCandidature.ACCEPTE.value: set(),
    StatutCandidature.REFUSE.value: set(),
}


async def create_candidature(data: dict, db, clinic_id: int = 1) -> Candidature:
    candidature = Candidature(
        clinic_id=clinic_id, poste=data["poste"], nom_candidat=data["nom_candidat"],
        email=data["email"], telephone=data.get("telephone"),
        cv_url=data.get("cv_url"), lettre_url=data.get("lettre_url"),
        statut=StatutCandidature.RECU.value,
    )
    db.add(candidature)
    await db.flush()
    return candidature


async def changer_statut(candidature_id: int, nouveau_statut: str, evaluateur_id: int, db,
                          notes_rh: Optional[str] = None, date_entretien: Optional[datetime] = None,
                          clinic_id: int | None = None) -> Candidature:
    stmt = select(Candidature).where(Candidature.id == candidature_id)
    if clinic_id is not None:
        stmt = stmt.where(Candidature.clinic_id == clinic_id)
    result = await db.execute(stmt)
    candidature = result.scalar_one_or_none()
    if not candidature:
        raise ValueError("Candidature non trouvée")

    autorises = TRANSITIONS_VALIDES.get(candidature.statut, set())
    if nouveau_statut not in autorises:
        raise ValueError(f"Transition invalide : {candidature.statut} → {nouveau_statut}")

    candidature.statut = nouveau_statut
    candidature.evaluateur_id = evaluateur_id
    if notes_rh:
        candidature.notes_rh = notes_rh
    if date_entretien:
        candidature.date_entretien = date_entretien

    await db.flush()
    return candidature


async def list_candidatures(db, statut: Optional[str] = None, poste: Optional[str] = None,
                       clinic_id: int | None = None) -> list[Candidature]:
    query = select(Candidature)
    if clinic_id is not None:
        query = query.where(Candidature.clinic_id == clinic_id)
    if statut:
        query = query.where(Candidature.statut == statut)
    if poste:
        query = query.where(Candidature.poste == poste)
    result = await db.execute(query.order_by(Candidature.created_at.desc()))
    return list(result.scalars().all())
