"""Seed idempotent de recette production pour AutoCommerce Clinic."""
from __future__ import annotations

import asyncio
import os
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from config import get_settings
from middleware.auth import get_password_hash
from models.database import (
    ActeMedical,
    LotInjectable,
    Patient,
    ProduitInjectable,
    RoleEnum,
    StatutLot,
    Utilisateur,
)


async def seed() -> None:
    settings = get_settings()
    engine = create_async_engine(settings.database_url)
    Session = async_sessionmaker(engine, expire_on_commit=False)

    async with Session() as db:
        qa_admin_email = os.getenv("QA_ADMIN_EMAIL", "admin@clinic.local")
        qa_admin_pwd = os.getenv("QA_ADMIN_PASSWORD")
        
        if not qa_admin_pwd and settings.env == "production":
            raise RuntimeError("QA_ADMIN_PASSWORD must be set in production seed")
        
        qa_admin_pwd = qa_admin_pwd or "ChangeMe123!"

        admin = (
            await db.execute(
                select(Utilisateur).where(Utilisateur.email == qa_admin_email)
            )
        ).scalar_one_or_none()
        if admin is None:
            admin = Utilisateur(
                clinic_id=1,
                email=qa_admin_email,
                hashed_password=get_password_hash(qa_admin_pwd),
                nom="Admin",
                prenom="QA",
                role=RoleEnum.DIRECTRICE.value,
                is_active=True,
            )
            db.add(admin)
        else:
            admin.hashed_password = get_password_hash(qa_admin_pwd)
            admin.role = RoleEnum.DIRECTRICE.value
            admin.is_active = True

        qa_medecin_email = os.getenv("QA_MEDECIN_EMAIL", "medecin@clinic.local")
        qa_medecin_pwd = os.getenv("QA_MEDECIN_PASSWORD")
        
        if not qa_medecin_pwd and settings.env == "production":
            raise RuntimeError("QA_MEDECIN_PASSWORD must be set in production seed")
            
        qa_medecin_pwd = qa_medecin_pwd or "ChangeMeMedecin123!"

        practitioner = (
            await db.execute(
                select(Utilisateur).where(Utilisateur.email == qa_medecin_email)
            )
        ).scalar_one_or_none()
        if practitioner is None:
            practitioner = Utilisateur(
                clinic_id=1,
                email=qa_medecin_email,
                hashed_password=get_password_hash(qa_medecin_pwd),
                nom="Ben Salem",
                prenom="Nadia",
                role=RoleEnum.MEDECIN.value,
                telephone="+21671123456",
                specialite="Médecine esthétique",
                agenda_color="#0F766E",
                is_active=True,
            )
            db.add(practitioner)
            await db.flush()

        acte = (
            await db.execute(
                select(ActeMedical).where(ActeMedical.nom == "Botox front - recette")
            )
        ).scalar_one_or_none()
        if acte is None:
            acte = ActeMedical(
                clinic_id=1,
                nom="Botox front - recette",
                categorie="injectable",
                duree_minutes=30,
                prix_base=Decimal("250.000"),
                description="Acte de recette pour validation du parcours de réservation.",
                is_active=True,
            )
            db.add(acte)
            await db.flush()

        patient = (
            await db.execute(
                select(Patient).where(Patient.telephone == "+21620000001")
            )
        ).scalar_one_or_none()
        if patient is None:
            patient = Patient(
                clinic_id=1,
                nom="Gharbi",
                prenom="Ines",
                telephone="+21620000001",
                whatsapp_phone="+21620000001",
                email="ines.gharbi@example.com",
                ville="Tunis",
                source_acquisition="seed_recette",
                statut="actif",
                is_active=True,
                points_fidelite=120,
                niveau_fidelite="gold",
            )
            db.add(patient)
            await db.flush()

        produit = (
            await db.execute(
                select(ProduitInjectable).where(ProduitInjectable.nom == "Botox Allergan - recette")
            )
        ).scalar_one_or_none()
        if produit is None:
            produit = ProduitInjectable(
                clinic_id=1,
                nom="Botox Allergan - recette",
                categorie="toxine",
                unite="unite",
                stock_minimum=Decimal("10.00"),
                stock_alerte=Decimal("20.00"),
            )
            db.add(produit)
            await db.flush()

        lot = (
            await db.execute(
                select(LotInjectable).where(LotInjectable.numero_lot == "QA-LOT-2026-001")
            )
        ).scalar_one_or_none()
        if lot is None:
            lot = LotInjectable(
                clinic_id=1,
                produit_id=produit.id,
                numero_lot="QA-LOT-2026-001",
                date_expiration=date.today() + timedelta(days=180),
                quantite_initiale=Decimal("100.00"),
                quantite_restante=Decimal("100.00"),
                statut=StatutLot.DISPONIBLE.value,
            )
            db.add(lot)

        await db.commit()
        print(
            f"Seed OK: admin={admin.id}, praticien={practitioner.id}, acte={acte.id}, "
            f"patient={patient.id}, produit={produit.id}, lot={lot.id if lot.id else 'new'}"
        )

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(seed())
