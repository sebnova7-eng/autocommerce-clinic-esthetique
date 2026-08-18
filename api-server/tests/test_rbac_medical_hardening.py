import pytest
from unittest.mock import MagicMock, AsyncMock
from services.patients import _serialize
from services.dossier_medical import get_timeline_patient

def test_directrice_cannot_see_sensitive_fields_in_patient_serialize():
    # Mock patient object
    patient = MagicMock()
    patient.id = 1
    patient.nom = "Doe"
    patient.prenom = "Jane"
    patient.allergies_enc = "encrypted_allergies"
    patient.antecedents_medicaux_enc = "encrypted_antecedents"
    patient.contre_indications_enc = "encrypted_contra"
    patient.note_interne_enc = "encrypted_note"
    patient.date_naissance = None
    patient.genre = None
    patient.telephone = "123456"
    patient.email = None
    patient.adresse = None
    patient.ville = None
    patient.groupe_sanguin = None
    patient.statut = "actif"
    patient.is_active = True
    patient.points_fidelite = 0
    patient.niveau_fidelite = "bronze"
    patient.derniere_visite = None
    patient.commercial_id = None
    patient.consentement_marketing = False
    patient.anonymized_at = None
    patient.created_at = None

    # Test for DIRECTRICE
    
    # We need to mock decrypt_field because it's used in _serialize
    with MagicMock():
        import services.patients
        original_decrypt = services.patients.decrypt_field
        services.patients.decrypt_field = lambda x: f"decrypted_{x}"
        
        # Test directrice
        res = _serialize(patient, include_sensitive=False, include_antecedents=False)
        assert "allergies" not in res
        assert "antecedents_medicaux" not in res
        assert "contre_indications" not in res
        assert "note_interne" not in res
        
        # Test medecin
        res_med = _serialize(patient, include_sensitive=True, include_antecedents=True)
        assert "allergies" in res_med
        assert res_med["allergies"] == "decrypted_encrypted_allergies"
        
        services.patients.decrypt_field = original_decrypt

@pytest.mark.asyncio
async def test_get_timeline_patient_masks_observations_for_directrice():
    # Mock DB and results
    db = AsyncMock()
    dossier = MagicMock()
    dossier.id = 101
    dossier.date_acte = MagicMock()
    dossier.date_acte.isoformat.return_value = "2026-01-01"
    dossier.observations_enc = "some_encrypted_data"
    dossier.zones_traitees = {}
    dossier.effets_secondaires = "some effects"
    dossier.satisfaction_patient = 5
    dossier.clinic_id = 1
    
    acte = MagicMock()
    acte.nom = "Botox"
    
    praticien = MagicMock()
    praticien.prenom = "Dr"
    praticien.nom = "House"
    
    mock_result = MagicMock()
    mock_result.all.return_value = [(dossier, acte, praticien)]
    mock_result.scalars.return_value.all.return_value = []
    
    db.execute.return_value = mock_result
    
    with MagicMock():
        import services.dossier_medical
        original_decrypt = services.dossier_medical.decrypt_field
        services.dossier_medical.decrypt_field = lambda x: "REAL_OBSERVATIONS"
        
        # Test for DIRECTRICE
        timeline = await get_timeline_patient(
            patient_id=1, db=db, user_role="directrice", clinic_id=1
        )
        
        assert len(timeline) == 1
        assert timeline[0]["observations"] == "[ACCÈS MÉDICAL RÉSERVÉ]"
        assert timeline[0]["effets_secondaires"] == "[ACCÈS RÉSERVÉ]"
        assert timeline[0]["photos"] == []
        
        # Test for MEDECIN
        timeline_med = await get_timeline_patient(
            patient_id=1, db=db, user_role="medecin", clinic_id=1
        )
        assert timeline_med[0]["observations"] == "REAL_OBSERVATIONS"
        assert timeline_med[0]["effets_secondaires"] == "some effects"
        
        services.dossier_medical.decrypt_field = original_decrypt

def test_directrice_has_no_access_to_photos_resource():
    from middleware.clinic_rbac import check_permission
    assert check_permission("directrice", "photos", "read") is False
    assert check_permission("directrice", "photos", "write") is False
    assert check_permission("directrice", "photos", "delete") is False
