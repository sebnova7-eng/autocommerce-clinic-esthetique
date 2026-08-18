import pytest
from datetime import datetime, timedelta
from decimal import Decimal
from models.database import Patient
from services.consommables import ConsommableService
from services.teleconsultation import TeleconsultationService
from services.parrainage import ParrainageService
from models.database import RendezVous

@pytest.mark.asyncio
async def test_consommables_stock_management(db, assistante):
    # 1. Création
    data = {
        "nom": "Gants examen M",
        "categorie": "Hygiène",
        "unite": "boite",
        "stock_actuel": 10,
        "seuil_alerte": 5,
        "stock_minimum": 2,
        "prix_unitaire": 15.5
    }
    c = await ConsommableService.create(db, data)
    assert c.nom == "Gants examen M"
    assert c.stock_actuel == Decimal("10.00")

    # 2. Mouvement Entrée
    await ConsommableService.add_mouvement(db, c.id, "entree", 5, assistante.id, "Réception commande")
    await db.refresh(c)
    assert c.stock_actuel == Decimal("15.00")

    # 3. Mouvement Sortie
    await ConsommableService.add_mouvement(db, c.id, "sortie", 2, assistante.id, "Utilisation soin")
    await db.refresh(c)
    assert c.stock_actuel == Decimal("13.00")

    # 4. Alertes
    c.stock_actuel = Decimal("4.00")
    await db.commit()
    alertes = await ConsommableService.get_alertes(db)
    assert len(alertes) > 0
    assert alertes[0]["niveau"] == "alerte"

@pytest.mark.asyncio
async def test_teleconsultation_flow(db, medecin, patient, acte):
    # 1. Créer un RDV
    rdv = RendezVous(
        clinic_id=1, patient_id=patient.id, praticien_id=medecin.id,
        acte_id=acte.id, date_heure_debut=datetime.utcnow() + timedelta(hours=1)
    )
    db.add(rdv)
    await db.flush()

    # 2. Créer téléconsultation
    tc = await TeleconsultationService.creer_pour_rdv(db, rdv.id)
    assert tc is not None
    assert "meet.jit.si" in tc.lien_visio
    assert tc.statut == "planifiee"

    # 3. Terminer
    success = await TeleconsultationService.marquer_terminee(db, tc.id, 25, "Patiente satisfaite")
    assert success is True
    await db.refresh(tc)
    assert tc.statut == "terminee"
    assert tc.duree_reelle == 25

@pytest.mark.asyncio
async def test_parrainage_system(db, patient):
    # 1. Créer code parrain
    code = await ParrainageService.get_ou_creer_code(db, patient.id)
    assert code is not None
    assert len(code) > 5

    # 2. Créer un filleul
    filleul = Patient(
        clinic_id=1, nom="Filleul", prenom="Test",
        telephone="+21699999999"
    )
    db.add(filleul)
    await db.flush()

    # 3. Utiliser code
    success = await ParrainageService.utiliser_code(db, code, filleul.id)
    assert success is True

    # 4. Vérifier points
    await db.refresh(patient)
    await db.refresh(filleul)
    assert patient.points_fidelite == 50
    assert filleul.points_fidelite == 50

    # 5. Vérifier parrainage enregistré
    filleuls = await ParrainageService.get_filleuls(db, patient.id)
    assert len(filleuls) == 1
    assert filleuls[0].filleul_patient_id == filleul.id
