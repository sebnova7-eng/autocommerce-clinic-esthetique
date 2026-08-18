"""
AutoCommerce Clinic — Audit log médical
Log chaque accès dossier médical. Conservation 10 ans, non modifiable.
"""

from typing import Optional

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from models.database import AuditLogMedical


async def log_medical_access(
    db: AsyncSession,
    utilisateur_id: int,
    patient_id: int,
    action: str,
    resource_type: str,
    resource_id: int,
    clinic_id: int = 1,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    details: Optional[dict] = None,
):
    """Enregistre un log d'accès médical.

    Non modifiable : pas d'UPDATE ni DELETE possible.
    Conservation 10 ans.

    Args:
        db: Session async
        utilisateur_id: ID de l'utilisateur ayant accédé
        patient_id: ID du patient concerné
        action: Action réalisée (ex: "CREATE_DOSSIER", "READ_PHOTO")
        resource_type: Type de ressource (ex: "dossier", "photo")
        resource_id: ID de la ressource
        ip_address: IP du client
        user_agent: User-Agent du client
        details: Détails additionnels (JSON)
    """
    log = AuditLogMedical(
        clinic_id=clinic_id,
        utilisateur_id=utilisateur_id,
        patient_id=patient_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        ip_address=ip_address,
        user_agent=user_agent,
        details=details or {},
    )
    db.add(log)
    await db.flush()


async def log_from_request(
    db: AsyncSession,
    request: Request,
    utilisateur_id: int,
    patient_id: int,
    action: str,
    resource_type: str,
    resource_id: int,
    clinic_id: int = 1,
    details: Optional[dict] = None,
):
    """Version simplifiée qui extrait IP et User-Agent de la requête."""
    ip = request.client.host if request.client else None
    ua = request.headers.get("user-agent")

    await log_medical_access(
        db=db,
        utilisateur_id=utilisateur_id,
        patient_id=patient_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        clinic_id=clinic_id,
        ip_address=ip,
        user_agent=ua,
        details=details,
    )
