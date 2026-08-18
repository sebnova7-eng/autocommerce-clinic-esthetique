"""Catalogue fermé des tools du Bloc 4."""

from typing import Any, Dict, List

TOOL_CATALOG: List[Dict[str, Any]] = [
    {
        "name": "search_patient",
        "resource": "patients",
        "action": "read",
        "sensitive": False,
        "description": "Recherche un patient par nom, prénom, téléphone ou email.",
        "parameters": {
            "type": "object",
            "properties": {"query": {"type": "string", "minLength": 1}},
            "required": ["query"],
            "additionalProperties": False,
        },
    },
    {
        "name": "create_rdv",
        "resource": "agenda",
        "action": "write",
        "sensitive": False,
        "description": "Crée un rendez-vous.",
        "parameters": {
            "type": "object",
            "properties": {
                "patient_id": {"type": "integer", "minimum": 1},
                "praticien_id": {"type": "integer", "minimum": 1},
                "acte_id": {"type": "integer", "minimum": 1},
                "date_heure": {"type": "string"},
                "salle": {"type": ["string", "null"]},
            },
            "required": ["patient_id", "praticien_id", "acte_id", "date_heure"],
            "additionalProperties": False,
        },
    },
    {
        "name": "update_rdv",
        "resource": "agenda",
        "action": "write",
        "sensitive": False,
        "description": "Modifie un rendez-vous existant.",
        "parameters": {
            "type": "object",
            "properties": {
                "rdv_id": {"type": "integer", "minimum": 1},
                "date_heure": {"type": "string"},
                "statut": {"type": "string", "enum": ["planifie", "confirme", "en_cours", "termine", "annule", "no_show"]},
                "notes_pre_acte": {"type": "string"},
                "notes_post_acte": {"type": "string"},
                "salle": {"type": ["string", "null"]},
            },
            "required": ["rdv_id"],
            "additionalProperties": False,
        },
    },
    {
        "name": "cancel_rdv",
        "resource": "agenda",
        "action": "delete",
        "sensitive": True,
        "description": "Annule un rendez-vous après confirmation obligatoire.",
        "parameters": {
            "type": "object",
            "properties": {
                "rdv_id": {"type": "integer", "minimum": 1},
                "raison": {"type": "string", "minLength": 3},
            },
            "required": ["rdv_id", "raison"],
            "additionalProperties": False,
        },
    },
    {
        "name": "send_whatsapp",
        "resource": "marketing",
        "action": "write",
        "sensitive": True,
        "description": "Envoie un WhatsApp à un patient après confirmation du contenu.",
        "parameters": {
            "type": "object",
            "properties": {
                "patient_id": {"type": "integer", "minimum": 1},
                "message": {"type": "string", "minLength": 1},
            },
            "required": ["patient_id", "message"],
            "additionalProperties": False,
        },
    },
    {
        "name": "send_email",
        "resource": "marketing",
        "action": "write",
        "sensitive": True,
        "description": "Envoie un email à un patient après confirmation.",
        "parameters": {
            "type": "object",
            "properties": {
                "patient_id": {"type": "integer", "minimum": 1},
                "subject": {"type": "string", "minLength": 1},
                "message": {"type": "string", "minLength": 1},
            },
            "required": ["patient_id", "subject", "message"],
            "additionalProperties": False,
        },
    },
    {
        "name": "launch_campaign",
        "resource": "marketing",
        "action": "write",
        "sensitive": True,
        "description": "Crée une campagne marketing après confirmation du périmètre.",
        "parameters": {
            "type": "object",
            "properties": {
                "nom": {"type": "string", "minLength": 1},
                "type": {"type": "string", "enum": ["whatsapp", "email", "sms"]},
                "message_template": {"type": "string", "minLength": 1},
                "segment_label": {"type": "string"},
            },
            "required": ["nom", "type", "message_template"],
            "additionalProperties": False,
        },
    },
    {
        "name": "get_statistics",
        "resource": "factures",
        "action": "read",
        "sensitive": False,
        "description": "Consulte les statistiques lecture seule héritées du Bloc 2.",
        "parameters": {
            "type": "object",
            "properties": {"periode": {"type": "string", "enum": ["semaine", "mois"]}},
            "additionalProperties": False,
        },
    },
    {
        "name": "create_internal_task",
        "resource": "marketing",
        "action": "write",
        "sensitive": False,
        "description": "Crée une tâche interne.",
        "parameters": {
            "type": "object",
            "properties": {
                "titre": {"type": "string", "minLength": 1},
                "description": {"type": "string"},
                "patient_id": {"type": "integer", "minimum": 1},
                "assignee_id": {"type": "integer", "minimum": 1},
                "priorite": {"type": "string", "enum": ["basse", "normale", "haute"]},
            },
            "required": ["titre"],
            "additionalProperties": False,
        },
    },
    {
        "name": "summarize_day",
        "resource": "agenda",
        "action": "read",
        "sensitive": False,
        "description": "Résumé lecture seule de la journée.",
        "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
    },
]

_TOOL_INDEX = {tool["name"]: tool for tool in TOOL_CATALOG}


def lookup_tool(name: str):
    return _TOOL_INDEX.get(name)


def known_tools() -> List[Dict[str, Any]]:
    return list(TOOL_CATALOG)
