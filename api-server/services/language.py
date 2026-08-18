"""Détection légère et déterministe de langue pour l’agent clinique.

Le message original n’est jamais remplacé : cette fonction sert uniquement à
choisir la langue de réponse et à conserver un signal de routage.
"""
from __future__ import annotations

import re

DARija_LATIN = {"nheb", "n7eb", "n7ot", "ma3ad", "chnowa", "win", "famma", "mouch", "moch", "bech", "ena", "kifech"}
ENGLISH = {"the", "and", "want", "book", "appointment", "please", "what", "where", "price", "clinic"}
ITALIAN = {"vorrei", "fissare", "appuntamento", "prezzo", "della", "clinica", "come", "grazie"}
GERMAN = {"ich", "möchte", "mochte", "termin", "buchen", "preis", "klinik", "bitte", "wo"}
FRENCH = {"bonjour", "voudrais", "prendre", "rendez", "vous", "prix", "clinique", "comment", "merci", "pourquoi"}


def detect_language(text: str) -> str:
    value = (text or "").strip().lower()
    if not value:
        return "fr"
    if any("\u0600" <= ch <= "\u06ff" for ch in value):
        return "darija"
    tokens = set(re.findall(r"[a-zàâçéèêëîïôûùüÿœ0-9']+", value))
    scores = {
        "darija": len(tokens & DARija_LATIN),
        "en": len(tokens & ENGLISH),
        "it": len(tokens & ITALIAN),
        "de": len(tokens & GERMAN),
        "fr": len(tokens & FRENCH),
    }
    best = max(scores, key=scores.get)
    return best if scores[best] else "fr"


def language_name(code: str) -> str:
    return {"fr": "français", "darija": "darija tunisienne", "en": "anglais", "it": "italien", "de": "allemand"}.get(code, "français")
