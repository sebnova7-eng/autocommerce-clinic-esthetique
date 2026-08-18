"""
Fixtures partagées — base SQLite en mémoire (aiosqlite), un jeu de
données de base (utilisateur, patient, acte, produit/lot) pour
chaque test, et un client HTTP factice pour les tests d'API légers.
"""
import os
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest_asyncio
from cryptography.fernet import Fernet
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.pool import StaticPool

# ── Config de test AVANT tout import de l'app ───────────────
TEST_DATA_ROOT = Path("/tmp/autocommerce-clinic-tests")
TEST_DATA_ROOT.mkdir(parents=True, exist_ok=True)
(TEST_DATA_ROOT / "data").mkdir(parents=True, exist_ok=True)
(TEST_DATA_ROOT / "photos").mkdir(parents=True, exist_ok=True)
(TEST_DATA_ROOT / "uploads").mkdir(parents=True, exist_ok=True)
(TEST_DATA_ROOT / "branding").mkdir(parents=True, exist_ok=True)
(TEST_DATA_ROOT / "backups").mkdir(parents=True, exist_ok=True)

os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite://")
os.environ.setdefault("REDIS_URL", "redis://:test-only@localhost:6379/0")
os.environ.setdefault("CORS_ORIGINS", "http://testserver")
os.environ.setdefault("FERNET_KEY", Fernet.generate_key().decode())
os.environ.setdefault("PHOTO_ENCRYPTION_KEY", Fernet.generate_key().decode())
os.environ.setdefault("SECRET_KEY", "test-secret-key-not-for-production-use-only-64-chars-minimum-ok")
os.environ.setdefault("ENV", "test")
os.environ.setdefault("PUBLIC_CLINIC_ID", "1")
os.environ.setdefault("WA_BUSINESS_TOKEN", "")
os.environ.setdefault("WA_PHONE_ID", "")
os.environ.setdefault("SOCIAL_WEBHOOK_SECRET", "")
os.environ.setdefault("DATA_DIR", str(TEST_DATA_ROOT / "data"))
os.environ.setdefault("PHOTOS_DIR", str(TEST_DATA_ROOT / "photos"))
os.environ.setdefault("UPLOADS_DIR", str(TEST_DATA_ROOT / "uploads"))
os.environ.setdefault("BRANDING_DIR", str(TEST_DATA_ROOT / "branding"))
os.environ.setdefault("BACKUPS_DIR", str(TEST_DATA_ROOT / "backups"))

from config import get_settings
get_settings.cache_clear()

# Disable rate limiting for tests (the real limiter is imported statically
# by route modules, so we cannot replace it — just disable it instead).
from api.deps import limiter as _test_limiter
_test_limiter.enabled = False

from models.database import (  # noqa: E402
    Base, Utilisateur, Patient, ActeMedical, Consentement, ProduitInjectable, LotInjectable, RoleEnum, StatutLot,
)

# Importer les nouveaux modèles Bloc 1 (omnicanal + sécurité)
# pour que Base.metadata les inclue dans create_all.
from models.omnicanal import (  # noqa: E402, F401
    ChannelConfig, Conversation, MessageOmnicanal, ChannelEvent,
)
from models.security import (  # noqa: E402, F401
    NumeroWhitelist, SessionAssistant, CommandeAssistant,
    ConfirmationSensible, AlerteSecurite, RefreshTokenSession,
)


@pytest_asyncio.fixture
async def engine():
    """Moteur SQLite en mémoire, partagé entre connexions (StaticPool)
    pour que toutes les sessions du test voient les mêmes tables."""
    eng = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    await eng.dispose()


@pytest_asyncio.fixture
async def db(engine):
    """Session async pour un test, avec flush mais rollback implicite
    (chaque test reçoit une base fraîche via la fixture `engine`)."""
    sessionmaker = async_sessionmaker(engine, expire_on_commit=False)
    async with sessionmaker() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def medecin(db):
    user = Utilisateur(
        clinic_id=1, email="medecin@clinic.tn", hashed_password="x",
        nom="Trabelsi", prenom="Sami", role=RoleEnum.MEDECIN.value,
    )
    db.add(user)
    await db.flush()
    return user


@pytest_asyncio.fixture
async def assistante(db):
    user = Utilisateur(
        clinic_id=1, email="assistante@clinic.tn", hashed_password="x",
        nom="Ben Ali", prenom="Rim", role=RoleEnum.ASSISTANTE.value,
    )
    db.add(user)
    await db.flush()
    return user


@pytest_asyncio.fixture
async def patient(db):
    p = Patient(
        clinic_id=1, nom="Gharbi", prenom="Ines",
        telephone="+21620000000", whatsapp_phone="+21620000000",
    )
    db.add(p)
    await db.flush()
    return p


@pytest_asyncio.fixture
async def acte(db):
    a = ActeMedical(
        clinic_id=1, nom="Botox front", categorie="injectable",
        duree_minutes=30, prix_base=Decimal("250.000"),
    )
    db.add(a)
    await db.flush()
    return a


@pytest_asyncio.fixture
async def produit(db):
    p = ProduitInjectable(
        clinic_id=1, nom="Botox Allergan", categorie="toxine",
        unite="unite", stock_minimum=Decimal("10.00"), stock_alerte=Decimal("20.00"),
    )
    db.add(p)
    await db.flush()
    return p


@pytest_asyncio.fixture
async def lot(db, produit):
    lot_record = LotInjectable(
        clinic_id=1, produit_id=produit.id, numero_lot="LOT-0001",
        date_expiration=date.today() + timedelta(days=180),
        quantite_initiale=Decimal("100.00"), quantite_restante=Decimal("100.00"),
        statut=StatutLot.DISPONIBLE.value,
    )
    db.add(lot_record)
    await db.flush()
    return lot_record


@pytest_asyncio.fixture
async def consentement_valide(db, patient, acte):
    c = Consentement(
        clinic_id=1, patient_id=patient.id, acte_id=acte.id,
        type_consentement="acte_medical", signe_le=datetime.utcnow(),
        methode_signature="tactile", est_valide=True,
    )
    db.add(c)
    await db.flush()
    return c
