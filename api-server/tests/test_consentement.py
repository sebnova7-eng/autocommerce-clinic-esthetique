"""Tests — services/consentement.py

Règle métier : un consentement n'est valide que s'il est signé
(est_valide=True) ET signé il y a moins de 12 mois.
"""
from datetime import datetime, timedelta

import pytest

from services.consentement import verify_consent, sign_consent
from models.database import Consentement


@pytest.mark.asyncio
async def test_no_consent_returns_false(db, patient, acte):
    assert await verify_consent(patient.id, acte.id, db) is False


@pytest.mark.asyncio
async def test_valid_recent_consent_returns_true(db, patient, acte, consentement_valide):
    assert await verify_consent(patient.id, acte.id, db) is True


@pytest.mark.asyncio
async def test_consent_older_than_12_months_is_invalid(db, patient, acte):
    old_consent = Consentement(
        clinic_id=1, patient_id=patient.id, acte_id=acte.id,
        type_consentement="acte_medical",
        signe_le=datetime.utcnow() - timedelta(days=400),
        methode_signature="tactile", est_valide=True,
    )
    db.add(old_consent)
    await db.flush()

    assert await verify_consent(patient.id, acte.id, db) is False


@pytest.mark.asyncio
async def test_consent_marked_invalid_is_not_accepted(db, patient, acte):
    revoked = Consentement(
        clinic_id=1, patient_id=patient.id, acte_id=acte.id,
        type_consentement="acte_medical", signe_le=datetime.utcnow(),
        methode_signature="tactile", est_valide=False,
    )
    db.add(revoked)
    await db.flush()

    assert await verify_consent(patient.id, acte.id, db) is False


@pytest.mark.asyncio
async def test_consent_for_different_acte_does_not_cover_this_one(db, patient, acte, consentement_valide):
    """Un consentement signé pour l'acte A ne doit pas couvrir l'acte B."""
    autre_acte_id = acte.id + 999  # acte inexistant, simule un acte différent
    assert await verify_consent(patient.id, autre_acte_id, db) is False


@pytest.mark.asyncio
async def test_sign_consent_creates_valid_record_and_sets_patient_rgpd_date(db, patient, acte, tmp_path, monkeypatch):
    from config import get_settings
    settings = get_settings()
    monkeypatch.setattr(settings, "data_dir", tmp_path)

    consentement = await sign_consent(
        patient_id=patient.id,
        acte_id=acte.id,
        signature_b64="data:image/png;base64,iVBORw0KGgo=",
        method="tactile",
        ip_address="10.0.0.1",
        db=db,
    )

    assert consentement.est_valide is True
    assert patient.consentement_rgpd_signe_le is not None
    assert await verify_consent(patient.id, acte.id, db) is True


@pytest.mark.asyncio
async def test_sign_consent_supports_simulation_ia_type(db, patient, tmp_path, monkeypatch):
    from config import get_settings
    settings = get_settings()
    monkeypatch.setattr(settings, "data_dir", tmp_path)

    consentement = await sign_consent(
        patient_id=patient.id,
        acte_id=None,
        signature_b64="data:image/png;base64,iVBORw0KGgo=",
        method="tactile",
        ip_address="10.0.0.1",
        db=db,
        type_consentement="simulation_ia",
    )

    assert consentement.type_consentement == "simulation_ia"
    assert consentement.est_valide is True
    assert "SIMULATION IA" in consentement.contenu_signe
    assert await verify_consent(patient.id, None, db, type_consentement="simulation_ia") == consentement


@pytest.mark.asyncio
async def test_sign_consent_acte_medical_requires_acte_id(db, patient, tmp_path, monkeypatch):
    from config import get_settings
    settings = get_settings()
    monkeypatch.setattr(settings, "data_dir", tmp_path)

    with pytest.raises(ValueError, match="acte_id"):
        await sign_consent(
            patient_id=patient.id,
            acte_id=None,
            signature_b64="data:image/png;base64,iVBORw0KGgo=",
            method="tactile",
            ip_address="10.0.0.1",
            db=db,
            type_consentement="acte_medical",
        )
