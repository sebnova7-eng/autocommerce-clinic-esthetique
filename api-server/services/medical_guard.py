"""Garde-fou médical de l'agent clinique (Bloc 7).

La classification est volontairement fail-closed pour les demandes à risque.
Elle ne constitue pas un avis médical : elle dirige les questions cliniques
vers un praticien et laisse l’agent gérer seulement l’information générale et
les actions administratives.
"""
from __future__ import annotations

import re
from enum import Enum


class MedicalLevel(str, Enum):
    INFO = "INFO"
    ACTION = "ACTION"
    ESCALADE = "ESCALADE"


ESCALATION_PATTERNS = (
    r"diagnos", r"prescri", r"posologie", r"dose", r"dosage", r"contre.?ind",
    r"allerg", r"complication", r"douleur", r"infection", r"effet secondaire",
    r"réaction", r"reaction", r"urgence", r"saigne", r"fièvre", r"fievre",
    r"résultat médical", r"resultat medical", r"traitement", r"médicament",
    r"medicament", r"normal après", r"normal apres", r"شنوة الدوا", r"وجيعة",
    r"حساسية", r"التهاب", r"جرعة", r"طبيب.*قال",
)

ACTION_PATTERNS = (
    r"rendez.?vous", r"rdv", r"annul", r"déplac", r"deplac", r"reprogram",
    r"facture", r"rappel", r"confirmer", r"prendre.*rendez", r"book.*appointment",
)


def classify_medical_request(text: str) -> MedicalLevel:
    value = (text or "").strip().lower()
    if any(re.search(pattern, value, flags=re.IGNORECASE) for pattern in ESCALATION_PATTERNS):
        return MedicalLevel.ESCALADE
    if any(re.search(pattern, value, flags=re.IGNORECASE) for pattern in ACTION_PATTERNS):
        return MedicalLevel.ACTION
    return MedicalLevel.INFO


def is_medical_escalation(text: str) -> bool:
    return classify_medical_request(text) == MedicalLevel.ESCALADE


def escalation_message(language: str = "fr") -> str:
    if language == "darija":
        return "هالطلب طبي وما نجمش نعطي تشخيص ولا دواء. يلزمك تتصل بالطبيب أو بالطوارئ إذا الحالة مستعجلة."
    if language == "en":
        return "This is a medical question. I cannot diagnose, prescribe, or assess an emergency. Please contact a doctor, or emergency services if urgent."
    if language == "it":
        return "Questa è una domanda medica. Non posso diagnosticare né prescrivere. Contatti un medico o i servizi di emergenza se è urgente."
    if language == "de":
        return "Das ist eine medizinische Frage. Ich darf keine Diagnose stellen oder Medikamente verschreiben. Bitte wenden Sie sich an einen Arzt oder im Notfall an den Rettungsdienst."
    return "Cette demande est médicale. Je ne peux pas établir de diagnostic, prescrire un traitement ni évaluer une urgence. Veuillez contacter un médecin ou les urgences si nécessaire."
