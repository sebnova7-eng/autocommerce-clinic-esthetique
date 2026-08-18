"""
AutoCommerce Clinic — Audit médical immuable
Insertion uniquement, pas d'UPDATE ni DELETE
"""

from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from models.database import AuditLogMedical


async def log_access(
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
    """Insère un log d'accès médical. Immuable."""
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
