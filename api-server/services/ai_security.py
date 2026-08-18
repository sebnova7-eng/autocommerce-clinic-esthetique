"""Politiques déterministes avant appel LLM ou exécution d'agent.

Les textes utilisateur, notes, messages et contextes sont des données non fiables.
Ce module ne remplace ni l'authentification ni le RBAC; il bloque seulement les
signaux de contournement à haut risque avant toute invocation IA.
"""
from __future__ import annotations

import re
from enum import Enum


class AISecurityDecision(str, Enum):
    ALLOW = "ALLOW"
    BLOCK_PROMPT_INJECTION = "BLOCK_PROMPT_INJECTION"
    BLOCK_SECRET_EXTRACTION = "BLOCK_SECRET_EXTRACTION"


PROMPT_INJECTION_PATTERNS = (
    r"ignore\s+(all\s+)?previous\s+instructions",
    r"ignore\s+(the\s+)?system\s+prompt",
    r"reveal\s+(the\s+)?(system|developer)\s+prompt",
    r"show\s+(me\s+)?(the\s+)?(system|developer)\s+message",
    r"instructions?\s+above",
    r"jailbreak",
    r"bypass\s+(the\s+)?(policy|guardrail|validation)",
    r"contourne[rz]?\s+(la\s+)?(politique|validation|sécurité)",
    r"révèle[rz]?\s+(le\s+)?prompt\s+système",
    r"ignore[rz]?\s+les\s+instructions",
)

SECRET_EXTRACTION_PATTERNS = (
    r"(?:reveal|show|give|print|export|send)\s+.*(?:api\s*key|secret|password|token|private\s+key)",
    r"(?:révèle|affiche|donne|exporte|envoie).*(?:clé\s+api|secret|mot\s+de\s+passe|token|clé\s+privée)",
    r"(?:api\s*key|secret|password|token|private\s+key)\s+(?:in|from|inside|dans|du)\s+(?:the\s+)?(?:prompt|context|system|server)",
)


def _matches(text: str, patterns: tuple[str, ...]) -> bool:
    value = (text or "").strip().lower()
    return any(re.search(pattern, value, flags=re.IGNORECASE | re.DOTALL) for pattern in patterns)


def evaluate_request(text: str) -> AISecurityDecision:
    if _matches(text, SECRET_EXTRACTION_PATTERNS):
        return AISecurityDecision.BLOCK_SECRET_EXTRACTION
    if _matches(text, PROMPT_INJECTION_PATTERNS):
        return AISecurityDecision.BLOCK_PROMPT_INJECTION
    return AISecurityDecision.ALLOW


def refusal_message(decision: AISecurityDecision) -> str:
    if decision == AISecurityDecision.BLOCK_SECRET_EXTRACTION:
        return "Je ne peux pas révéler de secrets, tokens, mots de passe ou clés privées."
    if decision == AISecurityDecision.BLOCK_PROMPT_INJECTION:
        return "Je ne peux pas suivre une instruction visant à contourner les règles de sécurité ou à révéler des instructions internes."
    return ""
