"""Tests — services/patients.py"""
import pytest

from services.patients import (
    create_patient, get_patient, list_patients, update_patient, anonymize_patient,
)
from models.database import Patient, Utilisateur, RoleEnum


@pytest.mark.asyncio
async def test_create_patient_encrypts_sensitive_fields(db):
    p = await create_patient({
        "nom": "Sassi", "prenom": "Amal", "telephone": "+21622111222",
        "allergies": "Pénicilline",
    }, db)
    assert p["allergies"] == "Pénicilline"

    result = await db.get(Patient, p["id"])
    assert result.allergies_enc != "Pénicilline"


@pytest.mark.asyncio
async def test_create_patient_rejects_duplicate_phone(db):
    await create_patient({"nom": "A", "prenom": "B", "telephone": "+21600000000"}, db)
    with pytest.raises(ValueError, match="existe déjà"):
        await create_patient({"nom": "C", "prenom": "D", "telephone": "+21600000000"}, db)


@pytest.mark.asyncio
async def test_get_patient_denies_unrelated_commercial(db):
    other_commercial = Utilisateur(clinic_id=1, email="c2@clinic.tn", hashed_password="x",
                                    nom="X", prenom="Y", role=RoleEnum.COMMERCIAL.value)
    db.add(other_commercial)
    await db.flush()

    p = await create_patient({"nom": "E", "prenom": "F", "telephone": "+21611111111",
                               "commercial_id": other_commercial.id + 999}, db)

    with pytest.raises(PermissionError):
        await get_patient(p["id"], {"role": "commercial", "id": other_commercial.id}, db)


@pytest.mark.asyncio
async def test_get_patient_allows_assigned_commercial(db):
    commercial = Utilisateur(clinic_id=1, email="c3@clinic.tn", hashed_password="x",
                              nom="X", prenom="Y", role=RoleEnum.COMMERCIAL.value)
    db.add(commercial)
    await db.flush()

    p = await create_patient({"nom": "G", "prenom": "H", "telephone": "+21622222222",
                               "commercial_id": commercial.id}, db)

    result = await get_patient(p["id"], {"role": "commercial", "id": commercial.id}, db)
    assert result["id"] == p["id"]


@pytest.mark.asyncio
async def test_get_patient_hides_sensitive_fields_from_commercial(db, patient):
    patient.commercial_id = 1
    await db.flush()
    result = await get_patient(patient.id, {"role": "commercial", "id": 1}, db)
    assert "allergies" not in result


@pytest.mark.asyncio
async def test_get_patient_hides_sensitive_fields_from_assistante(db, patient):
    result = await get_patient(patient.id, {"role": "assistante", "id": 1}, db)
    assert "allergies" not in result


@pytest.mark.asyncio
async def test_get_patient_shows_sensitive_fields_to_medecin(db, patient):
    result = await get_patient(patient.id, {"role": "medecin", "id": 1}, db)
    assert "allergies" in result


@pytest.mark.asyncio
async def test_list_patients_scopes_to_own_commercial(db):
    commercial = Utilisateur(clinic_id=1, email="c4@clinic.tn", hashed_password="x",
                              nom="X", prenom="Y", role=RoleEnum.COMMERCIAL.value)
    db.add(commercial)
    await db.flush()

    await create_patient({"nom": "Mine", "prenom": "A", "telephone": "+21633333333",
                           "commercial_id": commercial.id}, db)
    await create_patient({"nom": "NotMine", "prenom": "B", "telephone": "+21644444444"}, db)

    results = await list_patients({"role": "commercial", "id": commercial.id}, db)
    assert len(results) == 1
    assert results[0]["nom"] == "Mine"


@pytest.mark.asyncio
async def test_list_patients_excludes_anonymized(db, patient):
    await anonymize_patient(patient.id, db)
    results = await list_patients({"role": "admin", "id": 1}, db)
    assert patient.id not in [p["id"] for p in results]


@pytest.mark.asyncio
async def test_update_patient_re_encrypts_field(db, patient):
    updated = await update_patient(patient.id, {"antecedents_medicaux": "Diabète type 2"},
                                    {"role": "medecin", "id": 1}, db)
    assert updated["antecedents_medicaux"] == "Diabète type 2"


@pytest.mark.asyncio
async def test_anonymize_patient_strips_identifying_data(db, patient):
    result = await anonymize_patient(patient.id, db)
    assert result["nom"] == "Anonymisé"
    assert result["anonymized_at"] is not None

    await db.refresh(patient)
    assert patient.email is None
    assert patient.allergies_enc is None
    assert patient.is_active is False


@pytest.mark.asyncio
async def test_anonymize_unknown_patient_raises(db):
    with pytest.raises(ValueError, match="non trouvé"):
        await anonymize_patient(999999, db)
