"""
AutoCommerce Clinic — Catalogue de tools lecture seule (Bloc 2)
"""

from typing import Any, Dict, List

# ── Catalogue ──────────────────────────────────────────────
TOOL_CATALOG: List[Dict[str, Any]] = [
    {
        "name": "get_rdv_count_today",
        "intent": "consulter_agenda",
        "resource": "agenda",
        "action": "read",
        "description": "Donne le nombre de rendez-vous pour aujourd'hui.",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
            "additionalProperties": False
        },
        "strict": True
    },
    {
        "name": "get_next_rdv",
        "intent": "consulter_agenda",
        "resource": "agenda",
        "action": "read",
        "description": "Donne les détails du prochain rendez-vous.",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
            "additionalProperties": False
        },
        "strict": True
    },
    {
        "name": "list_rd_today",
        "intent": "consulter_agenda",
        "resource": "agenda",
        "action": "read",
        "description": "Liste les rendez-vous d'aujourd'hui.",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
            "additionalProperties": False
        },
        "strict": True
    },
    {
        "name": "send_daily_report",
        "intent": "consulter_infos_clinique",
        "resource": "agenda",
        "action": "read",
        "description": "Génère un rapport quotidien complet.",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
            "additionalProperties": False
        },
        "strict": True
    },
    {
        "name": "list_inactive_patients",
        "intent": "consulter_patient",
        "resource": "patients",
        "action": "read",
        "description": "Liste les patients inactifs depuis N mois.",
        "parameters": {
            "type": "object",
            "properties": {
                "since_months": {"type": "integer", "minimum": 1, "maximum": 36},
            },
            "required": ["since_months"],
            "additionalProperties": False,
        },
        "strict": True
    },
    {
        "name": "get_stock_overview",
        "intent": "consulter_stock",
        "resource": "stock_injectables",
        "action": "read",
        "description": "Donne l'état des stocks pour un produit ou globalement.",
        "parameters": {
            "type": "object",
            "properties": {
                "produit_nom": {"type": "string"},
            },
            "required": [],
            "additionalProperties": False,
        },
        "strict": True
    },
    {
        "name": "get_revenue_summary",
        "intent": "consulter_facture",
        "resource": "factures",
        "action": "read",
        "description": "Donne le résumé du chiffre d'affaires par période.",
        "parameters": {
            "type": "object",
            "properties": {
                "periode": {"type": "string", "enum": ["semaine", "mois"]},
            },
            "required": ["periode"],
            "additionalProperties": False,
        },
        "strict": True
    },
    {
        "name": "noop",
        "intent": "absorber_malveillance",
        "resource": "agenda",
        "action": "read",
        "description": "Outil vide pour absorber les requêtes non pertinentes ou malveillantes.",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
            "additionalProperties": False
        },
        "strict": True
    }
]

WRITE_INTENTS = {
    "annuler_rdv",
    "modifier_rdv",
    "creer_rdv",
    "envoyer_whatsapp",
    "envoyer_email",
    "lancer_campagne",
    "supprimer_patient",
    "rembourser",
    "anonymiser",
    "creer_tache",
}

REFUS_HORS_PERIMETRE_MESSAGE = (
    "Désolé, je suis un assistant en lecture seule. Je ne peux pas encore effectuer d'actions de modification ou d'envoi."
)
