import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from api.v1 import scribe_ia
from core.medical_ai_policy import MedicalAIBlocked, require_medical_ai_approval
from models.database import AuditLogMedical, MedicalScribeSession
from core.openai_audio import transcribe_audio_bytes
from services.assistant_security import log_assistant_command


def _approved_settings(**overrides):
    values = dict(
        env="test",
        clinic_id=None,
        is_internal_single_clinic=False,
        medical_ai_provider_approved=True,
        medical_ai_store_raw_transcription=False,
        llm_enabled=True,
        allowed_external_integrations={"ai"},
        llm_provider="openai",
        llm_provider_allowlist="openai",
        openai_api_key="test-key-not-real",
        openai_model="gpt-4o",
    )
    values.update(overrides)
    return SimpleNamespace(**values)


def test_medical_ai_is_fail_closed_by_default():
    settings = _approved_settings(medical_ai_provider_approved=False)
    with pytest.raises(MedicalAIBlocked, match="MEDICAL_AI_PROVIDER_APPROVED=false"):
        require_medical_ai_approval(settings, "test")


def test_approved_medical_provider_is_explicitly_allowed():
    require_medical_ai_approval(_approved_settings(), "test")


@pytest.mark.asyncio
async def test_medical_audio_blocks_before_provider_call(monkeypatch):
    settings = _approved_settings(medical_ai_provider_approved=False, openai_api_key="")
    provider_call = AsyncMock()
    monkeypatch.setattr("asyncio.to_thread", provider_call)

    with pytest.raises(MedicalAIBlocked):
        await transcribe_audio_bytes(
            settings,
            b"medical-audio",
            "scribe.webm",
            medical_data=True,
            budget_subject="clinic:1:user:1",
            budget_clinic_id=1,
        )
    provider_call.assert_not_awaited()


@pytest.mark.asyncio
async def test_scribe_wrong_tenant_is_denied_without_llm_call(monkeypatch, db, patient):
    monkeypatch.setattr(scribe_ia, "get_settings", lambda: _approved_settings())
    llm = AsyncMock()
    monkeypatch.setattr(scribe_ia, "get_llm_client", lambda settings: llm)

    payload = scribe_ia.ScribeGeneratePayload(
        patient_id=patient.id,
        transcription_brute="Patient décrit une gêne locale après consultation.",
    )
    with pytest.raises(HTTPException) as exc:
        await scribe_ia.process_medical_scribe(
            payload=payload,
            db=db,
            current_user={"id": 99, "clinic_id": 2, "role": "medecin"},
        )

    assert exc.value.status_code == 404
    llm.assert_not_awaited()


@pytest.mark.asyncio
async def test_scribe_approved_provider_does_not_store_raw_transcription_or_log_content(
    monkeypatch, db, medecin, patient
):
    settings = _approved_settings()
    monkeypatch.setattr(scribe_ia, "get_settings", lambda: settings)

    raw_medical = "Patient décrit une réaction clinique sensible et son historique médical."
    llm_response = SimpleNamespace(
        text=json.dumps({
            "subjective": "Symptôme décrit par le patient.",
            "objective": "Observation à confirmer.",
            "assessment": "Évaluation à confirmer par le praticien.",
            "plan": "Revue médicale obligatoire.",
        }),
        provider="openai",
        model="gpt-4o",
    )

    class FakeLLM:
        def __init__(self):
            self.messages = None

        async def chat(self, messages, **kwargs):
            self.messages = messages
            return llm_response

    fake_llm = FakeLLM()
    monkeypatch.setattr(scribe_ia, "get_llm_client", lambda settings: fake_llm)

    payload = scribe_ia.ScribeGeneratePayload(
        patient_id=patient.id,
        transcription_brute=raw_medical,
    )
    response = await scribe_ia.process_medical_scribe(
        payload=payload,
        db=db,
        current_user={"id": medecin.id, "clinic_id": 1, "role": "medecin"},
    )

    assert response.transcription_brute is None
    assert response.notes_structurees_soap["assessment"].startswith("Évaluation")
    stored = await db.scalar(select(MedicalScribeSession).where(MedicalScribeSession.id == response.scribe_id))
    assert stored is not None
    assert stored.transcription_brute is None

    audit = await db.scalar(
        select(AuditLogMedical).where(
            AuditLogMedical.resource_type == "medical_scribe_session",
            AuditLogMedical.resource_id == response.scribe_id,
        )
    )
    assert audit is not None
    audit_text = json.dumps(audit.details, ensure_ascii=False)
    assert raw_medical not in audit_text
    assert "test-key-not-real" not in audit_text
    assert "transcription_brute" not in audit_text
    assert fake_llm.messages is not None
    assert raw_medical in fake_llm.messages[1]["content"]


@pytest.mark.asyncio
async def test_scribe_default_policy_returns_503_without_provider_call(monkeypatch, db, patient):
    monkeypatch.setattr(
        scribe_ia,
        "get_settings",
        lambda: _approved_settings(medical_ai_provider_approved=False),
    )
    llm_factory = AsyncMock()
    monkeypatch.setattr(scribe_ia, "get_llm_client", llm_factory)
    payload = scribe_ia.ScribeGeneratePayload(
        patient_id=patient.id,
        transcription_brute="Texte clinique suffisant pour le test.",
    )

    with pytest.raises(HTTPException) as exc:
        await scribe_ia.process_medical_scribe(
            payload=payload,
            db=db,
            current_user={"id": 1, "clinic_id": 1, "role": "medecin"},
        )

    assert exc.value.status_code == 503
    llm_factory.assert_not_awaited()


@pytest.mark.asyncio
async def test_assistant_logs_keep_operational_metadata_only(db, medecin):
    raw = "Patient: nom, diagnostic, transcription sensible et secret sk-test-key"
    command = await log_assistant_command(
        db,
        session=None,
        current_user={"id": medecin.id, "clinic_id": 1, "role": "medecin"},
        numero="+21620000000",
        type_commande="audit",
        question=raw,
        statut="ok",
        reponse=raw,
        parametres={"patient_id": 42, "message": raw},
        tool_payload={"medical": raw},
        contexte={"original_message": raw, "provider": "openai"},
        erreur_message=raw,
    )

    assert command.question is None
    assert command.reponse is None
    assert command.tool_payload_json is None
    assert raw not in (command.parametres_appel or "")
    assert raw not in (command.contexte_json or "")
    assert "sk-test-key" not in (command.erreur_message or "")


def test_frontend_has_no_openai_key_or_secret_assignment():
    from pathlib import Path
    import re

    frontend = Path(__file__).resolve().parents[2].parent / "autocommerce-app" / "client" / "src"
    source = "\n".join(path.read_text(encoding="utf-8") for path in frontend.rglob("*.ts*"))
    assert "OPENAI_API_KEY" not in source
    assert not re.search(r"sk-(?:proj-)?[A-Za-z0-9_-]{20,}", source)
