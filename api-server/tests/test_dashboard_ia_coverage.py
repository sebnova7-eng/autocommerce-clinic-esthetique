import pytest
from models.database import NiveauFidelite
from services.dashboard_ia import DashboardIAService

@pytest.mark.asyncio
async def test_get_daily_summary(db, medecin):
    res = await DashboardIAService.get_daily_summary(db, user_id=medecin.id, clinic_id=1)
    assert "date" in res
    assert "rdvs_today_count" in res

@pytest.mark.asyncio
async def test_get_absent_patients(db, patient):
    # Patient with no last_visit_at is considered absent
    res = await DashboardIAService.get_absent_patients(db, clinic_id=1, days=30)
    assert res["total_absent_patients"] >= 1
    assert any(p["id"] == patient.id for p in res["patients"])

@pytest.mark.asyncio
async def test_get_vip_patients(db, patient):
    patient.niveau_fidelite = NiveauFidelite.VIP.value
    await db.flush()
    
    res = await DashboardIAService.get_vip_patients(db, clinic_id=1)
    assert res["total_vip"] >= 1
    assert any(p["id"] == patient.id for p in res["patients"])

@pytest.mark.asyncio
async def test_get_ai_recommendations(db):
    res = await DashboardIAService.get_ai_recommendations(db, clinic_id=1)
    assert "recommendations" in res
    assert len(res["recommendations"]) > 0

@pytest.mark.asyncio
async def test_get_revenue_forecast(db):
    res = await DashboardIAService.get_revenue_forecast(db, clinic_id=1, days=7)
    assert "forecast" in res
    assert len(res["forecast"]) == 7
