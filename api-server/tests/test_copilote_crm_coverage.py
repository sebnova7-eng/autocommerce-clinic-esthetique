import pytest
from datetime import datetime, timedelta
from models.database import DossierMedical, RendezVous, StatutRDV
from services.copilote_crm import CopiloteCRMService

@pytest.mark.asyncio
async def test_summarize_patient_file_not_found(db):
    res = await CopiloteCRMService.summarize_patient_file(db, patient_id=999)
    assert "error" in res

@pytest.mark.asyncio
async def test_summarize_patient_file_success(db, patient, medecin, acte):
    # Add a medical file entry
    dossier = DossierMedical(
        clinic_id=1, patient_id=patient.id, praticien_id=medecin.id,
        acte_id=acte.id, date_acte=datetime.utcnow(),
        satisfaction_patient=5
    )
    db.add(dossier)
    # Add a rendezvous
    rdv = RendezVous(
        clinic_id=1, patient_id=patient.id, praticien_id=medecin.id,
        acte_id=acte.id, date_heure_debut=datetime.utcnow() + timedelta(days=1),
        statut=StatutRDV.PLANIFIE.value,
        created_by=medecin.id
    )
    db.add(rdv)
    await db.flush()
    
    res = await CopiloteCRMService.summarize_patient_file(db, patient_id=patient.id)
    assert res["patient_id"] == patient.id
    assert "data" in res
    assert res["data"]["rdvs"]["total"] >= 1

@pytest.mark.asyncio
async def test_detect_at_risk_patients(db, patient):
    # Patient with no last_visit_at should be detected
    res = await CopiloteCRMService.detect_at_risk_patients(db, clinic_id=1)
    assert res["at_risk_count"] >= 1
    assert any(p["id"] == patient.id for p in res["items"])

@pytest.mark.asyncio
async def test_generate_medical_report(db, patient):
    res = await CopiloteCRMService.generate_medical_report(db, patient_id=patient.id)
    assert "draft_sections" in res
    assert res["patient_id"] == patient.id
