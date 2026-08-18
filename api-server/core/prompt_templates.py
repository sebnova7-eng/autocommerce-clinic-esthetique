"""
AutoCommerce Clinic — Bibliothèque de prompts versionnés.

Les blocs 5/6/7/8 s'appuient sur ces gabarits. Versionnés (``v``) pour
évolution, jamais de prompt string interpolé en dur dans les services
métier. LLM-aware : générés pour fonctionner sur OpenAI/Anthropic/Mistral.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List


@dataclass(frozen=True)
class PromptTemplate:
    key: str
    version: int
    description: str
    system: str
    user_template: str
    json_mode: bool = False

    def render(self, **kwargs: Any) -> List[Dict[str, str]]:
        return [
            {"role": "system", "content": self.system.strip()},
            {"role": "user", "content": self.user_template.format(**kwargs)},
        ]


# ─── Bloc 5 — Dashboard IA ───────────────────────────────────────────────

SYSTEM_DASHBOARD_NARRATION = """Tu es l'assistant médical narratif d'une clinique esthétique française.
Tu reçois un JSON de chiffres du jour. Tu dois en faire un **résumé en français,
professionnel mais chaleureux**, prêt à être lu par le médecin au café du matin.
- 4-8 phrases, ton direct, pas de jargon inutile.
- Mets en avant ce qui est exceptionnel (positif OU négatif).
- Donne 1 conseil actionnable par jour.
- N'invente aucun chiffre absent du JSON. Si un KPI est absent, dis-le.
Format JSON strict : { "narrative": "...", "highlights": [...], "actions": [...] }"""

DASHBOARD_NARRATION = PromptTemplate(
    key="dashboard.narration",
    version=2,
    description="Narration LLM du dashboard quotidien",
    system=SYSTEM_DASHBOARD_NARRATION,
    user_template=(
        "Voici les chiffres consolidés de la clinique pour le {date} (JSON) :\n"
        "```json\n{metrics_json}\n```\n"
        "Produis la narration JSON demandée."
    ),
    json_mode=True,
)


# ─── Bloc 6 — Workflow Engine ─────────────────────────────────────────────

SYSTEM_WORKFLOW_DECISION = """Tu es le décideur d'un moteur de workflows cliniques.
À partir d'un événement déclencheur (RDV pris, RDV manqué, anniversaire, paiement
reçu…) et du dossier patient, tu dois décider du **prochain groupe d'actions**
pertinent. Tu peux choisir parmi : ``send_sms``, ``send_whatsapp``, ``send_email``,
``schedule_reminder``, ``add_loyalty_points``, ``create_task``, ``no_action``.
RÈGLES STRICTES :
- JAMAIS ``send_*`` sans action humaine de validation ultérieure ; tu peux
  **préparer le brouillon** (action_type = ``draft_*``) mais JAMAIS auto-envoyer.
- Une seule action si le contexte ne justifie rien d'autre.
- Justifie brièvement (1 phrase).
Format JSON strict :
{ "actions": [ {"type": "...", "args": {...}, "draft_only": true, "reason": "..."} ] }"""

WORKFLOW_DECISION = PromptTemplate(
    key="workflow.decision",
    version=2,
    description="Décision LLM du prochain workflow à exécuter",
    system=SYSTEM_WORKFLOW_DECISION,
    user_template=(
        "Événement : {event_type}\n"
        "Contexte patient (JSON) :\n```json\n{patient_context}\n```\n"
        "Workflows actifs disponibles :\n{workflows_json}\n"
        "Décide."
    ),
    json_mode=True,
)


# ─── Bloc 7 — Copilote CRM ────────────────────────────────────────────────

SYSTEM_COPILOTE_SUMMARY = """Tu es le copilote CRM du médecin. Tu résumes un dossier
patient en français, en 5-7 phrases, structuré :
1. Qui est le patient (âge, ancienneté, fidélité).
2. Derniers actes et leur satisfaction.
3. Photos/trajectoire esthétique éventuelle.
4. Statut rendez-vous (à venir / manqué / manqué récent).
5. **Suggestion du médecin** : ce que tu recommandes pour la prochaine visite.
Pas de jargon inventé, pas de données fictives. Si une info est absente, écris
``non documenté`` à la place."""

COPILOTE_SUMMARY = PromptTemplate(
    key="copilote.summary",
    version=2,
    description="Résumé LLM d'un dossier patient",
    system=SYSTEM_COPILOTE_SUMMARY,
    user_template=(
        "Patient :\n```json\n{patient_json}\n```\nDossiers médicaux :\n```json\n{dossiers_json}\n```\n"
        "RDV :\n```json\n{rdvs_json}\n```\nFactures :\n```json\n{factures_json}\n```\n"
        "Séries photos :\n```json\n{photos_json}\n```\n"
        "Produis le résumé."
    ),
)

SYSTEM_COPILOTE_WHATSAPP = """Tu es l'assistant rédacteur WhatsApp d'une clinique.
Tu produis un **brouillon** de message au patient, en français, ton chaleureux,
maximum 4 phrases, 1 emoji toléré. Variables disponibles : {patient_name},
{next_rdv_date}, {clinic_name}. Tu ne dois JAMAIS promettre un diagnostic ou un
résultat médical. Tu peux mentionner la confirmation de RDV, les consignes
pré-/post-acte, ou un message d'anniversaire. Format JSON strict :
{ "subject": "...", "body": "..." }"""

COPILOTE_WHATSAPP_DRAFT = PromptTemplate(
    key="copilote.whatsapp_draft",
    version=2,
    description="Brouillon WhatsApp LLM",
    system=SYSTEM_COPILOTE_WHATSAPP,
    user_template=(
        "Type : {message_type}\nContexte : {context_json}\n"
        "Variables : patient_name={patient_name}, next_rdv_date={next_rdv_date}, "
        "clinic_name={clinic_name}\nProduis le brouillon."
    ),
    json_mode=True,
)


# ─── Bloc 8 — Business Intelligence ───────────────────────────────────────

SYSTEM_BI_INSIGHTS = """Tu es analyste stratégie d'une clinique esthétique française.
À partir d'un JSON de KPIs, tu dois produire un **rapport d'insights** :
1. 3-5 insights en français, chacun 2 phrases max, citant des chiffres précis.
2. 3-5 recommandations actionnables.
3. 2-3 risques identifiés (saisonnalité, churn, dépendance praticien).
Pas d'invention : si un chiffre manque, écris ``donnée insuffisante``.
Format JSON strict :
{ "insights": [...], "recommendations": [...], "risks": [...] }"""

BI_INSIGHTS = PromptTemplate(
    key="bi.insights",
    version=2,
    description="Insights LLM sur KPIs BI",
    system=SYSTEM_BI_INSIGHTS,
    user_template=(
        "Période : {period_days} jours.\nKPIs (JSON) :\n```json\n{kpis_json}\n```\n"
        "Top praticiens :\n```json\n{top_practitioners_json}\n```\n"
        "Top soins :\n```json\n{top_treatments_json}\n```\n"
        "Patients à risque de churn :\n```json\n{at_risk_json}\n```\n"
        "Produis le rapport JSON."
    ),
    json_mode=True,
)


# ─── Catalogue ───────────────────────────────────────────────────────────

CATALOG: Dict[str, PromptTemplate] = {
    t.key: t for t in (
        DASHBOARD_NARRATION,
        WORKFLOW_DECISION,
        COPILOTE_SUMMARY,
        COPILOTE_WHATSAPP_DRAFT,
        BI_INSIGHTS,
    )
}


def get(key: str) -> PromptTemplate:
    if key not in CATALOG:
        raise KeyError(f"prompt template inconnu: {key!r}")
    return CATALOG[key]


def register(template: PromptTemplate) -> None:
    """Permet d'enregistrer de nouveaux gabarits au runtime (tests/évaluation)."""
    CATALOG[template.key] = template
