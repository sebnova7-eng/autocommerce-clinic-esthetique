import pytest
from datetime import date, datetime, timedelta
from sqlalchemy import select
from models.database import ProduitInjectable
from services.stock_injectable import register_usage
from services.rappels_injection import process_injection_reminders

@pytest.mark.asyncio
async def test_register_usage_calculates_next_injection(db, lot, patient, medecin):
    # 1. Setup produit with duree_effet_jours
    result = await db.execute(select(ProduitInjectable).where(ProduitInjectable.id == lot.produit_id))
    produit = result.scalar_one()
    produit.duree_effet_jours = 90
    await db.flush()
    
    # 2. Register usage
    util = await register_usage(
        lot_id=lot.id,
        dossier_id=None,
        patient_id=patient.id,
        praticien_id=medecin.id,
        quantite=10,
        unite="unite",
        db=db
    )
    
    # 3. Assertions
    assert util.prochaine_injection_date is not None
    assert util.prochaine_injection_date == (date.today() + timedelta(days=90))
    assert util.prochaine_injection_envoyee is False

@pytest.mark.asyncio
async def test_process_injection_reminders(db, lot, patient, medecin):
    # 1. Setup produit
    result = await db.execute(select(ProduitInjectable).where(ProduitInjectable.id == lot.produit_id))
    produit = result.scalar_one()
    produit.duree_effet_jours = 90
    await db.flush()
    
    # 2. Create an utilization that is due today
    # We simulate an injection done 90 days ago
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
    
    # Force the date to today to be sure (in case of time shifts)
    util.prochaine_injection_date = date.today()
    await db.flush()
    
    # 3. Process reminders
    # Note: send_reply will return a mock success in test environment if no credentials
    count = await process_injection_reminders(db)
    
    # 4. Assertions
    assert count == 1
    assert util.prochaine_injection_envoyee is True
