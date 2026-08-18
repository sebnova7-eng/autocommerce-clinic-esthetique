from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from api.v1 import simulation_ia as simulation_api
from models.database import Consentement, Patient, PhotoClinic, SimulationIA
from services import simulation_morphing as morphing_service


@pytest.mark.asyncio
async def test_simulation_route_propagates_authenticated_clinic(monkeypatch):
    simulation = SimpleNamespace(id=44, created_at=datetime.utcnow())
    generate = AsyncMock(return_value=simulation)
    monkeypatch.setattr(simulation_api, "generer_simulation_ia", generate)

    payload = simulation_api.SimulationRequest(zone_anatomique="front", intensite=20)
    user = {"id": 7, "clinic_id": 10, "role": "medecin"}
    result = await simulation_api.post_simulation(
        patient_id=101,
        photo_id=202,
        data=payload,
        db=object(),
        current_user=user,
    )

    assert result["simulation_id"] == 44
    assert generate.await_args.kwargs["clinic_id"] == 10


@pytest.mark.asyncio
async def test_wrong_tenant_patient_is_denied_before_simulation(monkeypatch, db, patient):
    # The authenticated Clinic B context cannot create a simulation for Clinic A's patient.
    monkeypatch.setattr(morphing_service, "settings", SimpleNamespace(
        env="production",
        clinic_id=None,
        is_internal_single_clinic=False,
        medical_ai_provider_approved=True,
        llm_enabled=True,
        allowed_external_integrations={"ai"},
        llm_provider="openai",
        llm_provider_allowlist="openai",
        openai_api_key="test-key",
    ))

    with pytest.raises(ValueError, match="Patient non trouvé"):
        await morphing_service.generer_simulation_ia(
            patient_id=patient.id,
            photo_source_id=999,
            zone="front",
            intensite=20,
            genere_par_id=1,
            db=db,
            clinic_id=2,
        )


@pytest.mark.asyncio
async def test_clinic_a_reads_only_simulation_a(monkeypatch, db, medecin, patient):
    patient_b = Patient(
        clinic_id=2,
        nom="PatientB",
        prenom="CliniqueB",
        telephone="+21622000002",
    )
    db.add(patient_b)
    await db.flush()

    consent_a = Consentement(
        clinic_id=1,
        patient_id=patient.id,
        type_consentement="simulation_ia",
        signe_le=datetime.utcnow(),
        methode_signature="tactile",
        est_valide=True,
    )
    consent_b = Consentement(
        clinic_id=2,
        patient_id=patient_b.id,
        type_consentement="simulation_ia",
        signe_le=datetime.utcnow(),
        methode_signature="tactile",
        est_valide=True,
    )
    db.add_all([consent_a, consent_b])
    await db.flush()

    photo_a = PhotoClinic(
        clinic_id=1,
        patient_id=patient.id,
        type="avant",
        date_prise=datetime.utcnow(),
        url_stockage="/tmp/a.enc",
    )
    photo_b = PhotoClinic(
        clinic_id=2,
        patient_id=patient_b.id,
        type="avant",
        date_prise=datetime.utcnow(),
        url_stockage="/tmp/b.enc",
    )
    db.add_all([photo_a, photo_b])
    await db.flush()

    sim_a = SimulationIA(
        clinic_id=1,
        photo_source_id=photo_a.id,
        patient_id=patient.id,
        zone_anatomique="front",
        url_resultat="/tmp/sim_a.enc",
        consentement_id=consent_a.id,
        genere_par_id=medecin.id,
    )
    sim_b = SimulationIA(
        clinic_id=2,
        photo_source_id=photo_b.id,
        patient_id=patient_b.id,
        zone_anatomique="front",
        url_resultat="/tmp/sim_b.enc",
        consentement_id=consent_b.id,
        genere_par_id=medecin.id,
    )
    db.add_all([sim_a, sim_b])
    await db.flush()

    monkeypatch.setattr(morphing_service.os.path, "exists", lambda path: True)
    monkeypatch.setattr(morphing_service, "_decrypt_file", lambda nonce, ciphertext: b"jpg")
    monkeypatch.setattr(morphing_service, "log_access", AsyncMock())

    class DummyFile:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return b"0" * 12 + b"cipher"

    monkeypatch.setattr("builtins.open", lambda *args, **kwargs: DummyFile())
    monkeypatch.setattr(morphing_service, "settings", SimpleNamespace(
        env="production", clinic_id=None,
    ))

    data, _ = await morphing_service.get_decrypted_simulation(
        simulation_id=sim_a.id,
        patient_id=patient.id,
        clinic_id=1,
        db=db,
        utilisateur_id=medecin.id,
    )
    assert data == b"jpg"

    with pytest.raises(ValueError, match="Simulation non trouvée"):
        await morphing_service.get_decrypted_simulation(
            simulation_id=sim_b.id,
            patient_id=patient_b.id,
            clinic_id=1,
            db=db,
            utilisateur_id=medecin.id,
        )

    with pytest.raises(ValueError, match="Simulation non trouvée"):
        await morphing_service.get_decrypted_simulation(
            simulation_id=sim_a.id,
            patient_id=patient.id,
            clinic_id=2,
            db=db,
            utilisateur_id=medecin.id,
        )
