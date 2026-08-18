import pytest
from datetime import date, datetime, timedelta
from sqlalchemy import select
from models.database import ProduitInjectable, Patient
from services.stock_injectable import register_usage
from services.rappels_injection import process_injection_reminders
from unittest.mock import AsyncMock, patch

@pytest.mark.asyncio
async def test_process_injection_reminders_no_reminders_due(db, lot, patient, medecin):
    # Setup produit with duree_effet_jours
    result = await db.execute(select(ProduitInjectable).where(ProduitInjectable.id == lot.produit_id))
    produit = result.scalar_one()
    produit.duree_effet_jours = 90
    await db.flush()
    
    # Create an utilization that is NOT due yet
    future_date = datetime.utcnow() - timedelta(days=30) # 60 days left
    await register_usage(
        lot_id=lot.id,
        dossier_id=None,
        patient_id=patient.id,
        praticien_id=medecin.id,
        quantite=10,
        unite="unite",
        db=db,
        date_injection=future_date
    )
    
    count = await process_injection_reminders(db)
    assert count == 0

@pytest.mark.asyncio
async def test_process_injection_reminders_patient_no_whatsapp(db, lot, medecin):
    # Create a patient without whatsapp_phone
    patient_no_wa = Patient(
        clinic_id=1, nom="Doe", prenom="John",
        telephone="+21610000000", whatsapp_phone=None,
    )
    db.add(patient_no_wa)
    await db.flush()

    # Setup produit
    result = await db.execute(select(ProduitInjectable).where(ProduitInjectable.id == lot.produit_id))
    produit = result.scalar_one()
    produit.duree_effet_jours = 90
    await db.flush()
    
    # Create an utilization that is due today for patient without WA
    past_date = datetime.utcnow() - timedelta(days=90)
    util = await register_usage(
        lot_id=lot.id,
        dossier_id=None,
        patient_id=patient_no_wa.id,
        praticien_id=medecin.id,
        quantite=10,
        unite="unite",
        db=db,
        date_injection=past_date
    )
    util.prochaine_injection_date = date.today()
    await db.flush()
    
    count = await process_injection_reminders(db)
    assert count == 0
    assert util.prochaine_injection_envoyee is False # Should not be marked as sent

@pytest.mark.asyncio
async def test_process_injection_reminders_send_reply_fails(db, lot, patient, medecin):
    # Setup produit
    result = await db.execute(select(ProduitInjectable).where(ProduitInjectable.id == lot.produit_id))
    produit = result.scalar_one()
    produit.duree_effet_jours = 90
    await db.flush()
    
    # Create an utilization that is due today
    past_date = datetime.utcnow() - timedelta(days=90)
    util = await register_usage(
        lot_id=lot.id,
        dossier_id=None,
        patient_id=patient.id,
        praticien_id=medecin.id,
        quantite=10,
        unite="unite",
        db=db,
        date_injection=past_date
    )
    util.prochaine_injection_date = date.today()
    await db.flush()
    
    # Mock send_reply to simulate failure
    with patch('services.rappels_injection.send_reply', new_callable=AsyncMock) as mock_send_reply:
        mock_send_reply.return_value = {"message": None, "result": {"status": "failed"}}
        count = await process_injection_reminders(db)
        
        assert count == 0
        assert util.prochaine_injection_envoyee is False
        mock_send_reply.assert_called_once()

@pytest.mark.asyncio
async def test_register_usage_no_duree_effet_jours(db, lot, patient, medecin):
    # Setup produit with duree_effet_jours = 0
    result = await db.execute(select(ProduitInjectable).where(ProduitInjectable.id == lot.produit_id))
    produit = result.scalar_one()
    produit.duree_effet_jours = 0
    await db.flush()
    
    util = await register_usage(
        lot_id=lot.id,
        dossier_id=None,
        patient_id=patient.id,
        praticien_id=medecin.id,
        quantite=10,
        unite="unite",
        db=db
    )
    
    assert util.prochaine_injection_date is None
    assert util.prochaine_injection_envoyee is False

