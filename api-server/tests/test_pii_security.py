import pytest
from core.llm_client import pseudonymize_pii, LLMClient, LLMUnavailable

def test_pseudonymize_pii_recursive():
    raw_data = {
        "id": 1,
        "nom": "Jean Dupont",
        "email": "jean.dupont@example.com",
        "telephone": "0612345678",
        "notes": "Appeler au 0144556677 ou écrire à contact@test.com",
        "details": {
            "patient_name": "Marie Curie",
            "tel": "0788990011"
        },
        "list": [
            {"name": "Paul Martin", "phone": "0600000000"}
        ]
    }
    
    safe_data = pseudonymize_pii(raw_data)
    
    # Assertions
    assert safe_data["nom"] == "Jean D***"
    assert safe_data["email"] == "patient@email-masque.com"
    assert safe_data["telephone"] == "0612******"
    assert "0144556677" not in safe_data["notes"]
    assert "[TEL]" in safe_data["notes"]
    assert "contact@test.com" not in safe_data["notes"]
    assert "[EMAIL]" in safe_data["notes"]
    
    assert safe_data["details"]["patient_name"] == "Marie C***"
    assert safe_data["details"]["tel"] == "0788******"
    
    assert safe_data["list"][0]["name"] == "Paul M***"
    assert safe_data["list"][0]["phone"] == "0600******"

@pytest.mark.asyncio
async def test_llm_gate_disabled():
    class MockSettings:
        llm_enabled = False
        llm_provider = "openai"
        openai_api_key = "test-key"
    
    client = LLMClient(MockSettings())
    res = await client.chat([{"role": "user", "content": "hello"}])
    
    assert isinstance(res, LLMUnavailable)
    assert res.provider == "global"
    assert "désactivés" in res.reason
