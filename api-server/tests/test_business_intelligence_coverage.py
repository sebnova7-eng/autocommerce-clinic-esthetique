import pytest
from datetime import date, datetime
from decimal import Decimal
from models.database import Facture, StatutFacture, RendezVous, StatutRDV
from services.business_intelligence import BusinessIntelligenceService

@pytest.mark.asyncio
async def test_get_revenue_summary_empty(db):
    res = await BusinessIntelligenceService.get_revenue_summary(db, clinic_id=1, period_days=30)
    assert res["total_revenue"] == 0
    assert res["total_invoices"] == 0
    assert res["avg_invoice"] == 0

@pytest.mark.asyncio
async def test_get_revenue_summary_with_data(db, patient, medecin):
    # Create a paid invoice
    facture = Facture(
        clinic_id=1, patient_id=patient.id,
        numero_facture="F-2026-TEST",
        date_emission=date.today(),
        total_ttc=Decimal("100.000"),
        statut=StatutFacture.PAYEE.value,
        created_by=medecin.id
    )
    db.add(facture)
    await db.flush()
    
    res = await BusinessIntelligenceService.get_revenue_summary(db, clinic_id=1, period_days=30)
    assert res["total_revenue"] == 100.0
    assert res["total_invoices"] == 1

@pytest.mark.asyncio
async def test_get_top_practitioners_empty(db):
    res = await BusinessIntelligenceService.get_top_practitioners(db, clinic_id=1, period_days=30)
    assert "top_practitioners" in res

@pytest.mark.asyncio
async def test_get_top_practitioners_with_data(db, medecin, patient, acte):
    rdv = RendezVous(
        clinic_id=1, patient_id=patient.id, praticien_id=medecin.id,
        acte_id=acte.id, date_heure_debut=datetime.utcnow(),
        statut=StatutRDV.TERMINE.value,
        created_by=medecin.id
    )
    db.add(rdv)
    await db.flush()
    facture = Facture(
        clinic_id=1, patient_id=patient.id, rdv_id=rdv.id,
        numero_facture="F-2026-BI-1", date_emission=date.today(),
        total_ttc=Decimal("500.000"), created_by=medecin.id,
        statut=StatutFacture.PAYEE.value
    )
    db.add(facture)
    await db.flush()
    
    res = await BusinessIntelligenceService.get_top_practitioners(db, clinic_id=1, period_days=30)
    assert len(res["top_practitioners"]) > 0
    assert res["top_practitioners"][0]["revenue"] == 500.0

@pytest.mark.asyncio
async def test_get_top_treatments_with_data(db, medecin, patient, acte):
    rdv = RendezVous(
        clinic_id=1, patient_id=patient.id, praticien_id=medecin.id,
        acte_id=acte.id, date_heure_debut=datetime.utcnow(),
        statut=StatutRDV.TERMINE.value,
        created_by=medecin.id
    )
    db.add(rdv)
    await db.flush()
    facture = Facture(
        clinic_id=1, patient_id=patient.id, rdv_id=rdv.id,
        numero_facture="F-2026-BI-2", date_emission=date.today(),
        total_ttc=Decimal("300.000"), created_by=medecin.id,
        statut=StatutFacture.PAYEE.value
    )
    db.add(facture)
    await db.flush()
    
    res = await BusinessIntelligenceService.get_top_treatments(db, clinic_id=1, period_days=30)
    assert len(res["top_treatments"]) > 0
    assert res["top_treatments"][0]["revenue"] == 300.0

@pytest.mark.asyncio
async def test_get_kpi_dashboard(db):
    res = await BusinessIntelligenceService.get_kpi_dashboard(db, clinic_id=1)
    assert "revenue_today" in res
    assert "revenue_month" in res
    assert "rdv_today" in res
