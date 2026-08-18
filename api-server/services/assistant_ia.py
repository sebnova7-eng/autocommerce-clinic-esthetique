"""Assistant WhatsApp lecture seule — Bloc 2."""

from __future__ import annotations

import logging
import re
from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from models.security import TypeCommandeAssistantEnum
from services.assistant_security import get_or_create_session, log_assistant_command, check_rate_limit, MAX_PAYLOAD_SIZE_KB
from services.assistant_tools import lookup_tool, run_tool
from services.assistant_tools_schema import REFUS_HORS_PERIMETRE_MESSAGE, WRITE_INTENTS

logger = logging.getLogger("assistant_ia")

SYSTEM_PROMPT = (
    "Tu es l'assistant IA de la clinique AutoCommerce. Ton rôle est STRICTEMENT limité à la LECTURE "
    "des données (RDV, stocks, CA). Tu ne peux en aucun cas modifier le dossier patient, "
    "créer des rendez-vous ou envoyer des messages. Si l'utilisateur te demande une action, "
    "réponds poliment que tu n'as pas les droits pour modifier les données."
)

_REGEX_INTENT_TOOL: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\b(combien|combien de)\b.*\b(rdv|rendez[- ]vous)\b.*\b(aujourd|aujourd'hui)\b"), "get_rdv_count_today"),
    (re.compile(r"\b(rapport|synth[èe]se|bilan)\b.*\b(du jour|aujourd|journalier)\b"), "send_daily_report"),
    (re.compile(r"\b(prochain|suivant)\b.*\b(rdv|rendez[- ]vous|patient)\b"), "get_next_rdv"),
    (re.compile(r"\b(liste|d[ée]tails?)\b.*\b(rdv|rendez[- ]vous)\b.*\b(aujourd|aujourd'hui)\b"), "list_rd_today"),
    (re.compile(r"\b(inactifs?|pas consult|pas vus?|perdus?)\b.*\b(patient)s?\b"), "list_inactive_patients"),
    (re.compile(r"\b(patient)s?\b.*\b(inactifs?|pas consult|pas vus?|perdus?)\b"), "list_inactive_patients"),
    (re.compile(r"\b(stock|injectable|restant|botox|acide|produit)\b"), "get_stock_overview"),
    (re.compile(r"\b(ca|chiffre d.?affaire|revenu|recette)\b.*\b(semaine|7 jours|huit jours|mois|30 jours)\b"), "get_revenue_summary"),
]

_REGEX_WRITE_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\b(annul|supprim|d[ée]programm)\w*\b.*\b(rdv|rendez[- ]vous|patient)\b"), "annuler_rdv"),
    (re.compile(r"\bcr[ée]er?\w*\b.*\b(rdv|rendez[- ]vous)\b"), "creer_rdv"),
    (re.compile(r"\b(modifi|reprogramm|d[ée]plac)\w*\b.*\b(rdv|rendez[- ]vous)\b"), "modifier_rdv"),
    (re.compile(r"\b(envoie|envoy)\w*\b.*\b(whatsapp|message|sms|email|mail)\b"), "envoyer_whatsapp"),
    (re.compile(r"\b(lance?r?|programme?r?)\w*\b.*\b(campagne|publicit)\w*\b"), "lancer_campagne"),
    (re.compile(r"\bcr[ée]er?\w*\b.*\bt(ache|âche|odo)\b"), "creer_tache"),
]

# ── Darija (arabe dialectal tunisien/maghrébin, graphie arabe) ──
# Le darija n'a pas d'orthographe standardisée (variantes selon la région,
# préfixes/suffixes collés) : on matche des racines par sous-chaîne plutôt
# que par \b + mot exact comme pour le français, pour rester tolérant aux
# variations d'écriture les plus courantes sur WhatsApp.
_DARIJA_INTENT_TOOL: list[tuple[list[str], str]] = [
    (["قداش", "شحال"], "get_rdv_count_today"),  # combiné avec موعد plus bas
    (["تقرير", "ملخص اليوم", "ملخص النهار"], "send_daily_report"),
    (["الجاي", "التالي"], "get_next_rdv"),  # combiné avec موعد/حريف plus bas
    (["قائمة المواعيد", "لائحة المواعيد"], "list_rd_today"),
    (["ما جاوش", "غايبين", "ما زاروش"], "list_inactive_patients"),
    (["ستوك", "بوتوکس", "بوتوكس", "الحقن"], "get_stock_overview"),
    (["دخل", "رقم الأعمال", "مداخيل"], "get_revenue_summary"),
]

_DARIJA_WRITE_PATTERNS: list[tuple[list[str], str]] = [
    (["الغي", "نحي", "احذف"], "annuler_rdv"),  # + موعد
    (["زيد موعد", "عمل موعد", "أعمل موعد", "ضيف موعد"], "creer_rdv"),
    (["بدل الموعد", "غير الموعد", "أخر الموعد"], "modifier_rdv"),
    (["ابعث", "صيفط", "ارسل"], "envoyer_whatsapp"),  # + رسالة/واتساب
    (["اطلق حملة", "ابعث حملة", "حملة تسويق"], "lancer_campagne"),
    (["زيد مهمة", "عمل مهمة", "ضيف مهمة"], "creer_tache"),
]

_MAWAID_TERMS = ["موعد", "مواعيد", "حريف", "حرفاء", "الحريف"]


def _detect_darija_intent(text: str) -> Optional[tuple[str, dict[str, Any]]]:
    """Retourne (tool_or_intent, params) si une intention darija matche,
    None sinon. Volontairement séparée de _detect_intent pour rester
    lisible — les deux langues ont des heuristiques différentes."""
    for keywords, intent in _DARIJA_WRITE_PATTERNS:
        if any(k in text for k in keywords) and any(m in text for m in _MAWAID_TERMS + ["رسالة", "واتساب", "حملة", "مهمة"]):
            return intent, {}
        # lancer_campagne / creer_tache ont déjà le contexte dans leurs propres mots-clés
        if intent in ("lancer_campagne", "creer_tache") and any(k in text for k in keywords):
            return intent, {}

    for keywords, tool in _DARIJA_INTENT_TOOL:
        if any(k in text for k in keywords):
            # get_rdv_count_today / get_next_rdv ont besoin du contexte موعد
            if tool in ("get_rdv_count_today", "get_next_rdv") and not any(m in text for m in _MAWAID_TERMS):
                continue
            params: dict[str, Any] = {}
            if tool == "get_stock_overview" and ("بوتوکس" in text or "بوتوكس" in text):
                params["produit_nom"] = "Botox"
            if tool == "get_revenue_summary":
                params["periode"] = "mois" if "الشهر" in text else "semaine"
            return tool, params
    return None

def _detect_intent(question: str) -> tuple[str, dict[str, Any]]:
    text = (question or "").strip().lower()

    # Texte contenant de l'écriture arabe : on tente le darija d'abord —
    # les patterns français (\bmot\b latin) ne matcheront jamais dessus
    # de toute façon, mais on garde les deux heuristiques bien séparées.
    if any("\u0600" <= ch <= "\u06FF" for ch in text):
        darija_result = _detect_darija_intent(text)
        if darija_result:
            return darija_result

    for pattern, intent in _REGEX_WRITE_PATTERNS:
        if pattern.search(text):
            return intent, {}
    for pattern, tool in _REGEX_INTENT_TOOL:
        if pattern.search(text):
            params: dict[str, Any] = {}
            if tool == "list_inactive_patients":
                m = re.search(r"(\d{1,2})\s*mois", text)
                params["since_months"] = int(m.group(1)) if m else 6
            if tool == "get_stock_overview":
                if "botox" in text:
                    params["produit_nom"] = "Botox"
            if tool == "get_revenue_summary":
                params["periode"] = "mois" if ("mois" in text or "30 jours" in text) else "semaine"
            return tool, params
    return "unknown", {}

def _detect_lang(text: str) -> str:
    """"darija" si le texte contient de l'écriture arabe, "fr" sinon.
    Pas de détection plus fine (darija vs arabe standard) : sur WhatsApp,
    dans ce contexte clinique, les deux se traitent avec les mêmes
    réponses en darija — plus naturel que du MSA formel pour un message
    professionnel court."""
    return "darija" if any("\u0600" <= ch <= "\u06FF" for ch in (text or "")) else "fr"


def _humanize(tool: str, payload: dict[str, Any], lang: str = "fr") -> str:
    if lang == "darija":
        if tool == "get_rdv_count_today":
            return f"عندك {payload.get('count', 0)} موعد اليوم."
        if tool == "get_next_rdv":
            rdv = payload.get("rdv")
            if not rdv:
                return "ما فماش موعد جاي."
            return f"الموعد الجاي : {rdv.get('heure', '؟')} مع {rdv.get('patient', 'حريف غير معروف')}."
        if tool == "list_rd_today":
            rdvs = payload.get("rdvs") or []
            if not rdvs:
                return "ما فماش موعد اليوم."
            lignes = [f"- {r['heure']} : {r['patient']} ({r['statut']})" for r in rdvs]
            return f"عندك {len(rdvs)} موعد اليوم :\n" + "\n".join(lignes)
        if tool == "list_inactive_patients":
            return f"{payload.get('count', 0)} حريف ما جاوش من {payload.get('since_months', 6)} أشهر."
        if tool == "get_stock_overview":
            return f"عندك {payload.get('total_alertes', 0)} تنبيه في الستوك."
        if tool == "get_revenue_summary":
            return f"رقم الأعمال {payload.get('periode')} : {payload.get('ca_ttc', 0):.2f} دينار ({payload.get('nb_factures', 0)} فاتورة)."
        if tool == "noop":
            return "ما نجمش نجاوب على هالطلب بالضبط."
        return "الطلب تعالج."

    if tool == "get_rdv_count_today":
        return f"Vous avez {payload.get('count', 0)} rendez-vous aujourd'hui."
    if tool == "get_next_rdv":
        rdv = payload.get("rdv")
        if not rdv:
            return "Aucun prochain rendez-vous trouvé."
        return f"Prochain RDV : {rdv.get('heure', '?')} avec {rdv.get('patient', 'patient inconnu')}."
    if tool == "list_rd_today":
        rdvs = payload.get("rdvs") or []
        if not rdvs:
            return "Aucun rendez-vous aujourd'hui."
        lignes = [f"- {r['heure']} : {r['patient']} ({r['statut']})" for r in rdvs]
        return f"Vos {len(rdvs)} RDV d'aujourd'hui :\n" + "\n".join(lignes)
    if tool == "list_inactive_patients":
        return f"{payload.get('count', 0)} patient(s) sans visite depuis {payload.get('since_months', 6)} mois."
    if tool == "get_stock_overview":
        return f"{payload.get('total_alertes', 0)} alerte(s) stock."
    if tool == "get_revenue_summary":
        return f"CA {payload.get('periode')} : {payload.get('ca_ttc', 0):.2f} DT ({payload.get('nb_factures', 0)} factures)."
    if tool == "noop":
        return "Je ne peux pas répondre à cette demande spécifique."
    return "Demande traitée."

async def handle_whatsapp_message(
    numero: str,
    question: str,
    current_user: dict[str, Any],
    db: AsyncSession,
    *,
    conversation_id: Optional[int] = None,
) -> dict[str, Any]:
    # 1. Check Rate Limit
    if not await check_rate_limit(numero, db):
        msg = "عندك بزاف طلبات، استنى دقيقة." if _detect_lang(question) == "darija" else "Trop de requêtes. Veuillez patienter une minute."
        return {"reponse": msg, "statut": "rate_limited"}

    # 2. Check Payload Size
    if len(question.encode()) > MAX_PAYLOAD_SIZE_KB * 1024:
        msg = "الرسالة طويلة برشا." if _detect_lang(question) == "darija" else "Message trop long."
        return {"reponse": msg, "statut": "payload_too_large"}

    intent, parameters = _detect_intent(question)
    lang = _detect_lang(question)
    session = await get_or_create_session(numero, current_user, db)

    if intent in WRITE_INTENTS:
        msg = (REFUS_HORS_PERIMETRE_MESSAGE if lang != "darija" else
               "سامحني، أنا مساعد نقرا برك الميعطياتي، ما نجمش نبدل حاجة ولا نبعث حاجة توا.")
        await log_assistant_command(db, session=session, current_user=current_user, numero=numero,
                                    type_commande=TypeCommandeAssistantEnum.HORS_PERIMETRE.value,
                                    question=question, statut="refuse", reponse=msg,
                                    intent_detecte=intent, raison_refus="Lecture seule")
        return {"reponse": msg, "statut": "refuse"}

    if not lookup_tool(intent) and intent not in ("unknown", "noop"):
        intent = "noop"

    if intent == "unknown":
        msg = ("ما فهمتش طلبك. نجم نعطيك معلومات على المواعيد، رقم الأعمال ولا الستوك."
               if lang == "darija" else
               "Je n'ai pas compris votre demande. Je peux vous renseigner sur les RDV, le CA ou les stocks.")
        await log_assistant_command(db, session=session, current_user=current_user, numero=numero,
                                    type_commande=intent, question=question, statut="unknown",
                                    reponse=msg, intent_detecte=intent)
        return {"reponse": msg, "statut": "unknown"}

    try:
        payload = await run_tool(intent, parameters, current_user, db)
        reponse = _humanize(intent, payload, lang)
        
        # PII Scrubbing in logs via log_assistant_command (handled in service)
        await log_assistant_command(db, session=session, current_user=current_user, numero=numero,
                                    type_commande=intent, question=question, statut="ok", reponse=reponse,
                                    intent_detecte=intent, outil_appele=intent, parametres=parameters,
                                    tool_payload=payload)
        return {"reponse": reponse, "statut": "ok"}
    except Exception as e:
        logger.error(f"Assistant error: {e}")
        err_msg = "صار مشكل، جرب مرة أخرى." if lang == "darija" else "Une erreur est survenue."
        # Logger aussi les erreurs pour le rate limiting
        await log_assistant_command(db, session=session, current_user=current_user, numero=numero,
                                    type_commande=intent, question=question, statut="error",
                                    reponse=err_msg, intent_detecte=intent)
        return {"reponse": err_msg, "statut": "error"}
