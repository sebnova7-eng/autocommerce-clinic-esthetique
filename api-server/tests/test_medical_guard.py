from services.medical_guard import MedicalLevel, classify_medical_request, escalation_message


def test_general_information_is_allowed():
    assert classify_medical_request("Quels sont vos horaires et le prix du Botox ?") == MedicalLevel.INFO


def test_administrative_action_is_allowed_with_confirmation():
    assert classify_medical_request("Je voudrais prendre un rendez-vous") == MedicalLevel.ACTION


def test_medical_questions_escalate():
    for text in (
        "Quelle posologie dois-je prendre ?",
        "Est-ce une allergie ou une infection ?",
        "Pouvez-vous diagnostiquer cette douleur ?",
        "هل هذه حساسية وما هي الجرعة؟",
    ):
        assert classify_medical_request(text) == MedicalLevel.ESCALADE


def test_escalation_is_multilingual():
    assert "medical" in escalation_message("en").lower()
    assert "medica" in escalation_message("it").lower()
    assert "medizin" in escalation_message("de").lower()
    assert "médicale" in escalation_message("fr").lower()
    assert "طبي" in escalation_message("darija")
