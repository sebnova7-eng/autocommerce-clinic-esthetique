"""
AutoCommerce Clinic — Service Fidélité

Gestion des points (gain/dépense), recalcul du niveau, historique.
"""
from typing import Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from models.database import Patient, FideliteTransaction, NiveauFidelite

# Seuils de points pour chaque niveau (bornes basses)
NIVEAUX_SEUILS = [
    (5000, NiveauFidelite.VIP.value),
    (2000, NiveauFidelite.GOLD.value),
    (500, NiveauFidelite.SILVER.value),
    (0, NiveauFidelite.BRONZE.value),
]


def _niveau_pour(points: int) -> str:
    for seuil, niveau in NIVEAUX_SEUILS:
        if points >= seuil:
            return niveau
    return NiveauFidelite.BRONZE.value


async def _get_patient(patient_id: int, db: AsyncSession, lock: bool = False) -> Patient:
    query = select(Patient).where(Patient.id == patient_id)
    if lock:
        # Verrou ligne pour les opérations qui modifient le solde de points :
        # deux requêtes concurrentes (ex : gain WhatsApp + dépense caisse en
        # même temps) ne doivent pas lire le même solde de départ.
        query = query.with_for_update()
    result = await db.execute(query)
    patient = result.scalar_one_or_none()
    if not patient:
        raise ValueError("Patient non trouvé")
    return patient


async def add_points(patient_id: int, points: int, motif: str, db: AsyncSession,
                      reference_id: Optional[int] = None, reference_type: Optional[str] = None, clinic_id: int = 1) -> FideliteTransaction:
    """points > 0 pour un gain. Le niveau est recalculé automatiquement."""
    patient = await _get_patient(patient_id, db, lock=True)

    patient.points_fidelite += points
    patient.niveau_fidelite = _niveau_pour(patient.points_fidelite)

    tx = FideliteTransaction(
        clinic_id=clinic_id, patient_id=patient_id, type="gain",
        points=points, solde_apres=patient.points_fidelite,
        motif=motif, reference_id=reference_id, reference_type=reference_type,
    )
    db.add(tx)
    await db.flush()
    return tx


async def redeem_points(patient_id: int, points: int, motif: str, db: AsyncSession, clinic_id: int = 1) -> FideliteTransaction:
    """Dépense de points (ex : réduction). Refuse si solde insuffisant."""
    patient = await _get_patient(patient_id, db, lock=True)

    if points > patient.points_fidelite:
        raise ValueError("Solde de points insuffisant")

    patient.points_fidelite -= points
    patient.niveau_fidelite = _niveau_pour(patient.points_fidelite)

    tx = FideliteTransaction(
        clinic_id=clinic_id, patient_id=patient_id, type="depense",
        points=-points, solde_apres=patient.points_fidelite, motif=motif,
    )
    db.add(tx)
    await db.flush()
    return tx


async def get_historique(patient_id: int, db: AsyncSession) -> list[FideliteTransaction]:
    result = await db.execute(
        select(FideliteTransaction)
        .where(FideliteTransaction.patient_id == patient_id)
        .order_by(FideliteTransaction.created_at.desc())
    )
    return list(result.scalars().all())


async def get_overview(db: AsyncSession, limit: int = 100) -> dict:
    """Vue d'ensemble fidélité toutes patientes confondues : solde total
    et transactions les plus récentes avec le nom de la patiente.

    Manquait entièrement : la page frontend appelait GET /fidelite, qui
    n'a jamais existé (seul /fidelite/{patient_id}/historique existait,
    par patiente) — 404 systématique sur la page Fidélité."""
    total_result = await db.execute(
        select(func.coalesce(func.sum(Patient.points_fidelite), 0)).where(Patient.anonymized_at.is_(None))
    )
    total_points = total_result.scalar_one()

    tx_result = await db.execute(
        select(FideliteTransaction, Patient)
        .join(Patient, Patient.id == FideliteTransaction.patient_id)
        .order_by(FideliteTransaction.created_at.desc())
        .limit(limit)
    )
    transactions = [
        {
            "id": tx.id,
            "patient_nom": f"{patient.prenom} {patient.nom}",
            "type": tx.type,
            "points": tx.points,
            "motif": tx.motif,
            "date": tx.created_at,
        }
        for tx, patient in tx_result.all()
    ]
    return {"total_points": total_points, "transactions": transactions}
