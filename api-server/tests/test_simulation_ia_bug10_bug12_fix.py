from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from api.v1 import simulation_ia as simulation_api
from services import simulation_morphing as morphing_service


@pytest.mark.asyncio
async def test_sign_simulation_ia_consent_helper_uses_simulation_ia_type(monkeypatch):
    fake_consent = SimpleNamespace(
        id=42,
        type_consentement="simulation_ia",
        est_valide=True,
        signe_le=SimpleNamespace(isoformat=lambda: "2026-07-29T00:00:00"),
    )

    sign_mock = AsyncMock(return_value=fake_consent)
    monkeypatch.setattr(simulation_api, "sign_consent", sign_mock)

    request = SimpleNamespace(client=SimpleNamespace(host="127.0.0.1"))
    payload = simulation_api.SimulationIAConsentRequest(signature_base64="data:image/png;base64,AAAA")

    result = await simulation_api._sign_simulation_ia_consent(
        patient_id=5,
        data=payload,
        request=request,
        db=object(),
    )

    assert result["type_consentement"] == "simulation_ia"
    assert sign_mock.await_args.kwargs["type_consentement"] == "simulation_ia"


@pytest.mark.asyncio
async def test_get_decrypted_simulation_logs_read_access(monkeypatch):
    sim = SimpleNamespace(
        id=3,
        patient_id=9,
        url_resultat="/tmp/sim.enc",
        zone_anatomique="lèvres",
    )

    class FakeResult:
        def scalar_one_or_none(self):
            return sim

    class FakeDB:
        async def execute(self, *args, **kwargs):
            return FakeResult()

    AsyncMock()
    log_mock = AsyncMock()

    monkeypatch.setattr(morphing_service.os.path, "exists", lambda path: True)
    monkeypatch.setattr(morphing_service, "log_access", log_mock)
    monkeypatch.setattr(morphing_service, "_decrypt_file", lambda nonce, ciphertext: b"jpg")

    class DummyFile:
        def __enter__(self):
            return self
        def __exit__(self, exc_type, exc, tb):
            return False
        def read(self):
            return b"0" * 12 + b"cipher"

    monkeypatch.setattr("builtins.open", lambda *args, **kwargs: DummyFile())

    data, filename = await morphing_service.get_decrypted_simulation(
        simulation_id=3,
        patient_id=9,
        db=FakeDB(),
        utilisateur_id=77,
        ip_address="10.0.0.1",
        user_agent="pytest",
    )

    assert data == b"jpg"
    assert filename == "simulation_3.jpg"
    assert log_mock.await_count == 1
    assert log_mock.await_args.kwargs["action"] == "READ_IA_SIMULATION"
