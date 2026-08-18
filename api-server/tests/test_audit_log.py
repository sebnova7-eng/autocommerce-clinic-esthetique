"""Tests — middleware/audit_log.py & services/audit_medical.py

L'audit log médical doit tracer chaque accès. Ces tests vérifient
la création des entrées ; l'immuabilité (pas d'UPDATE/DELETE) est
garantie par le fait qu'aucune fonction du module n'expose une
opération de mise à jour ou de suppression (vérifié ici par
introspection).
"""
import inspect

import pytest
from sqlalchemy import select

from middleware.audit_log import log_medical_access
from services import audit_medical
from models.database import AuditLogMedical


@pytest.mark.asyncio
async def test_log_medical_access_creates_entry(db, medecin, patient):
    await log_medical_access(
        db=db, utilisateur_id=medecin.id, patient_id=patient.id,
        action="READ_DOSSIER", resource_type="dossier", resource_id=1,
        ip_address="10.0.0.1", user_agent="pytest",
    )
    result = await db.execute(select(AuditLogMedical))
    logs = result.scalars().all()
    assert len(logs) == 1
    assert logs[0].action == "READ_DOSSIER"
    assert logs[0].details == {}


@pytest.mark.asyncio
async def test_log_medical_access_stores_details_json(db, medecin, patient):
    await log_medical_access(
        db=db, utilisateur_id=medecin.id, patient_id=patient.id,
        action="READ_PHOTO", resource_type="photo", resource_id=5,
        details={"zone": "front", "acte_id": 3},
    )
    result = await db.execute(select(AuditLogMedical))
    log = result.scalars().first()
    assert log.details == {"zone": "front", "acte_id": 3}


def test_audit_medical_module_exposes_no_update_or_delete():
    """L'audit médical doit être append-only : aucune fonction publique
    de mise à jour/suppression ne doit exister dans ce module."""
    names = [name for name, _ in inspect.getmembers(audit_medical, inspect.isfunction)]
    forbidden = [n for n in names if any(k in n.lower() for k in ("update", "delete", "remove", "edit"))]
    assert forbidden == []
