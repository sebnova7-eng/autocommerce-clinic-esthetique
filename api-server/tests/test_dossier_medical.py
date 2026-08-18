"""Tests — services/dossier_medical.py

Couvre le chiffrement Fernet des observations et la règle métier la
plus critique : impossible de créer un dossier médical sans
consentement signé et valide.
"""
import pytest

from services.dossier_medical import (
    encrypt_field, decrypt_field, create_dossier, get_timeline_patient,
)
from models.database import AuditLogMedical
from sqlalchemy import select


# ── Chiffrement ───────────────────────────────────────────────

def test_encrypt_decrypt_roundtrip():
    plaintext = "Antécédent : allergie lidocaïne"
    ciphertext = encrypt_field(plaintext)
    assert ciphertext != plaintext
    assert decrypt_field(ciphertext) == plaintext


def test_encrypt_empty_string_returns_empty():
    assert encrypt_field("") == ""


def test_decrypt_empty_string_returns_empty():
    assert decrypt_field("") == ""


def test_ciphertext_is_not_plaintext_substring():
    """Vérifie qu'aucun fragment lisible du texte original ne traîne
    dans le ciphertext (Fernet = AES + HMAC, donc déjà garanti, mais
    on verrouille le comportement observable)."""
    plaintext = "DonneeSensibleUnique12345"
    ciphertext = encrypt_field(plaintext)
    assert plaintext not in ciphertext


# ── create_dossier : garde-fou consentement ──────────────────

@pytest.mark.asyncio
async def test_create_dossier_fails_without_consent(db, patient, medecin, acte):
    with pytest.raises(ValueError, match="[Cc]onsentement"):
        await create_dossier(
            patient_id=patient.id,
            praticien_id=medecin.id,
            rdv_id=None,
            data={"acte_id": acte.id, "observations": "test"},
            db=db,
        )


@pytest.mark.asyncio
async def test_create_dossier_succeeds_with_valid_consent(db, patient, medecin, acte, consentement_valide):
    dossier = await create_dossier(
        patient_id=patient.id,
        praticien_id=medecin.id,
        rdv_id=None,
        data={"acte_id": acte.id, "observations": "Bonne tolérance"},
        db=db,
    )
    assert dossier.id is not None
    # Les observations doivent être chiffrées en base, jamais en clair
    assert dossier.observations_enc != "Bonne tolérance"
    assert decrypt_field(dossier.observations_enc) == "Bonne tolérance"


@pytest.mark.asyncio
async def test_create_dossier_writes_audit_log(db, patient, medecin, acte, consentement_valide):
    dossier = await create_dossier(
        patient_id=patient.id,
        praticien_id=medecin.id,
        rdv_id=None,
        data={"acte_id": acte.id, "observations": "obs"},
        db=db,
        ip_address="10.0.0.5",
    )
    result = await db.execute(
        select(AuditLogMedical).where(AuditLogMedical.resource_id == dossier.id)
    )
    log = result.scalar_one_or_none()
    assert log is not None
    assert log.action == "CREATE_DOSSIER"
    assert log.patient_id == patient.id
    assert log.ip_address == "10.0.0.5"


@pytest.mark.asyncio
async def test_create_dossier_without_observations_leaves_field_none(db, patient, medecin, acte, consentement_valide):
    dossier = await create_dossier(
        patient_id=patient.id,
        praticien_id=medecin.id,
        rdv_id=None,
        data={"acte_id": acte.id},
        db=db,
    )
    assert dossier.observations_enc is None


@pytest.mark.asyncio
async def test_get_timeline_patient_decrypts_observations(db, patient, medecin, acte, consentement_valide):
    await create_dossier(
        patient_id=patient.id, praticien_id=medecin.id, rdv_id=None,
        data={"acte_id": acte.id, "observations": "Rougeur légère 24h"},
        db=db,
    )
    timeline = await get_timeline_patient(patient.id, db)
    assert len(timeline) == 1
    assert timeline[0]["observations"] == "Rougeur légère 24h"


@pytest.mark.asyncio
async def test_get_timeline_patient_empty_for_unknown_patient(db):
    timeline = await get_timeline_patient(999999, db)
    assert timeline == []


@pytest.mark.asyncio
async def test_get_timeline_patient_logs_read_access_when_user_provided(db, patient, medecin, acte, consentement_valide):
    await create_dossier(
        patient_id=patient.id, praticien_id=medecin.id, rdv_id=None,
        data={"acte_id": acte.id, "observations": "obs"}, db=db,
    )
    await get_timeline_patient(patient.id, db, utilisateur_id=medecin.id, ip_address="10.0.0.9")

    result = await db.execute(
        select(AuditLogMedical).where(AuditLogMedical.action == "READ_TIMELINE")
    )
    log = result.scalar_one_or_none()
    assert log is not None
    assert log.utilisateur_id == medecin.id
    assert log.ip_address == "10.0.0.9"


@pytest.mark.asyncio
async def test_get_timeline_patient_does_not_log_without_user(db, patient):
    await get_timeline_patient(patient.id, db)
    result = await db.execute(select(AuditLogMedical))
    assert result.scalars().all() == []
