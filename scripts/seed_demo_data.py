import asyncio
import os
import sys
from decimal import Decimal

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
API_SERVER_DIR = os.path.join(PROJECT_ROOT, "api-server")
sys.path.insert(0, API_SERVER_DIR)

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from middleware.auth import get_password_hash
from models.database import ActeMedical, ClinicSetting, RoleEnum, Utilisateur

DATABASE_URL = os.environ["DATABASE_URL"]
DEMO_PASSWORD = os.getenv("DEMO_PASSWORD", "DemoClinic!2026")

USERS = [
    ("admin.demo@clinique-esthetique.local", "Admin", "Demo", RoleEnum.ADMIN.value, "Administrateur plateforme", "#334155"),
    ("direction.demo@clinique-esthetique.local", "Direction", "Demo", RoleEnum.DIRECTRICE.value, "Direction de clinique", "#0EA5A4"),
    ("medecin.demo@clinique-esthetique.local", "Médecin", "Demo", RoleEnum.MEDECIN.value, "Médecine esthétique", "#8B5CF6"),
    ("estheticienne.demo@clinique-esthetique.local", "Esthéticienne", "Demo", RoleEnum.ESTHETICIENNE.value, "Soins esthétiques", "#EC4899"),
    ("assistante.demo@clinique-esthetique.local", "Assistante", "Demo", RoleEnum.ASSISTANTE.value, "Accueil et coordination", "#F59E0B"),
    ("commercial.demo@clinique-esthetique.local", "Commercial", "Demo", RoleEnum.COMMERCIAL.value, "Relation patient", "#10B981"),
]

ACTES = [
    ("Consultation esthétique", "consultation", 45, "Évaluation personnalisée et plan de soins esthétique.", Decimal("80.000")),
    ("Peeling nouvelle génération", "soin_visage", 45, "Soin de renouvellement cutané adapté au profil du patient.", Decimal("150.000")),
    ("Soin visage premium", "soin_visage", 60, "Soin visage personnalisé avec protocole de confort.", Decimal("120.000")),
    ("Injection esthétique", "injectable", 30, "Acte esthétique réalisé après consultation médicale et consentement.", Decimal("250.000")),
    ("Laser esthétique", "laser", 45, "Séance laser selon indication et protocole validé.", Decimal("220.000")),
]

async def main() -> None:
    engine = create_async_engine(DATABASE_URL, pool_pre_ping=True)
    Session = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with Session() as db:
        branding = {
            "nom_clinique": "Clinique Esthétique Demo",
            "logo_url": None,
            "couleur_primaire": "#0EA5A4",
            "couleur_secondaire": "#172126",
            "contenu_landing": {
                "titre": "Bienvenue",
                "sous_titre": "Votre clinique esthétique de confiance",
                "services_mis_en_avant": ["Consultation esthétique", "Soin visage premium", "Injection esthétique"],
                "adresse": "Adresse de démonstration — environnement synthétique",
                "telephone": "+216 70 000 000",
                "horaires": "Lundi–Samedi, 09:00–18:00",
            },
        }
        setting = (await db.execute(select(ClinicSetting).where(ClinicSetting.clinic_id == 1, ClinicSetting.key == "branding"))).scalar_one_or_none()
        if setting:
            setting.value = branding
            setting.description = "Branding esthétique de démonstration"
        else:
            db.add(ClinicSetting(clinic_id=1, key="branding", value=branding, description="Branding esthétique de démonstration"))

        for email, nom, prenom, role, specialite, color in USERS:
            user = (await db.execute(select(Utilisateur).where(Utilisateur.email == email))).scalar_one_or_none()
            if not user:
                user = Utilisateur(
                    clinic_id=1,
                    email=email,
                    hashed_password=get_password_hash(DEMO_PASSWORD),
                    nom=nom,
                    prenom=prenom,
                    role=role,
                    telephone="+21670000000",
                    specialite=specialite,
                    agenda_color=color,
                    is_active=True,
                )
                db.add(user)
            else:
                user.clinic_id = 1
                user.role = role
                user.specialite = specialite
                user.is_active = True

        for nom, categorie, duree, description, prix in ACTES:
            acte = (await db.execute(select(ActeMedical).where(ActeMedical.clinic_id == 1, ActeMedical.nom == nom))).scalar_one_or_none()
            if not acte:
                db.add(ActeMedical(clinic_id=1, nom=nom, categorie=categorie, duree_minutes=duree, description=description, prix_base=prix, is_active=True))
            else:
                acte.categorie = categorie
                acte.duree_minutes = duree
                acte.description = description
                acte.prix_base = prix
                acte.is_active = True
        await db.commit()
        print("SEEDED_USERS", len(USERS))
        print("SEEDED_ACTES", len(ACTES))
        print("DEMO_PASSWORD", DEMO_PASSWORD)
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
