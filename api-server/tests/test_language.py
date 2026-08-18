from services.language import detect_language


def test_detect_french():
    assert detect_language("Bonjour, je voudrais prendre rendez-vous.") == "fr"


def test_detect_tunisian_darija_arabic():
    assert detect_language("نحب ناخو موعد") == "darija"


def test_detect_tunisian_darija_latin_and_numbers():
    assert detect_language("nheb n7ot rdv") == "darija"
    assert detect_language("chnowa prix botox") == "darija"


def test_detect_english_italian_german():
    assert detect_language("I want to book an appointment") == "en"
    assert detect_language("Vorrei fissare un appuntamento") == "it"
    assert detect_language("Ich möchte einen Termin buchen") == "de"


def test_mixed_french_darija_keeps_darija_signal():
    assert detect_language("Bonjour, nheb n7ot rdv") == "darija"
