"""Ajoute des données synthétiques pour une seconde clinique de test."""
from __future__ import annotations

import asyncio
import os

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from config import get_settings
from middleware.auth import get_password_hash
from models.database import Patient, RoleEnum, Utilisateur


async def main() -> None:
    settings = get_settings()
    engine = create_async_engine(settings.database_url)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as db:
        user = await db.scalar(select(Utilisateur).where(Utilisateur.email == "admin@clinic-b.local"))
        clinic_b_password = os.environ.get("QA_CLINIC_B_PASSWORD")
        if not clinic_b_password:
            raise RuntimeError("QA_CLINIC_B_PASSWORD requis hors dépôt")
        if user is None:
            user = Utilisateur(
                clinic_id=2,
                email="admin@clinic-b.local",
                hashed_password=get_password_hash(clinic_b_password),
                nom="AdminB",
                prenom="Clinic",
                role=RoleEnum.DIRECTRICE.value,
                is_active=True,
            )
            db.add(user)
        else:
            user.clinic_id = 2
            user.is_active = True
            user.hashed_password = get_password_hash(clinic_b_password)

        patient = await db.scalar(select(Patient).where(Patient.email == "patient-b@example.com"))
        if patient is None:
            patient = Patient(
                clinic_id=2,
                nom="PatientB",
                prenom="Synthetic",
                telephone="+21620000002",
                email="patient-b@example.com",
                source_acquisition="tenant_isolation_test",
                statut="actif",
                is_active=True,
            )
            db.add(patient)
        else:
            patient.clinic_id = 2
        await db.commit()
        print(f"TENANT_B user_id={user.id} patient_id={patient.id}")
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
