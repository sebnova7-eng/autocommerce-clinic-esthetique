from api.v1.assistant_ia import REGISTERED_AGENT_TOOL_NAMES
from core.agent_runtime import ToolRegistry, sanitize_user_context


def test_capabilities_source_of_truth_is_explicit():
    assert REGISTERED_AGENT_TOOL_NAMES == ("search_patient", "revenue_30d", "draft_whatsapp", "at_risk_patients")


def test_sensitive_context_is_not_forwarded():
    ctx = sanitize_user_context({"patient_id": 4, "numero_piece": "ABC", "email": "x@y.tn", "name": "A"})
    assert ctx == {"patient_id": 4, "name": "A"}


def test_empty_registry_has_no_phantom_tools():
    assert ToolRegistry().names() == []


def test_readiness_does_not_expose_database_details():
    from pathlib import Path
    source = Path(__file__).parents[1].joinpath("main.py").read_text()
    assert 'content={"status": "not_ready"}' in source
    assert '"db": "ok"' not in source
    assert 'DB non disponible:' not in source


def test_metrics_route_is_protected():
    from pathlib import Path
    source = Path(__file__).parents[1].joinpath("main.py").read_text()
    assert 'Depends(require_role(RoleEnum.ADMIN, RoleEnum.DIRECTRICE))' in source


def test_medical_photo_encryption_is_authenticated():
    import pytest
    from services.photos_clinic import _encrypt_file, _decrypt_file
    data = b"medical-photo-bytes"
    nonce, ciphertext = _encrypt_file(data)
    assert _decrypt_file(nonce, ciphertext) == data
    tampered = ciphertext[:-1] + bytes([ciphertext[-1] ^ 1])
    with pytest.raises(Exception):
        _decrypt_file(nonce, tampered)
