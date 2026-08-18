"""AI Clinic Agent — Bloc 4 avec confirmation, RBAC et sessions."""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from models.security import TypeCommandeAssistantEnum
from services.language import detect_language
from services.medical_guard import escalation_message, is_medical_escalation


def _detect_lang(text: str) -> str:
    """Détecte la langue sans modifier le message original."""
    return detect_language(text)


from services.assistant_security import (
    consume_confirmation_if_valid,
    create_confirmation,
    get_or_create_session,
    get_session_context,
    log_assistant_command,
    set_session_context,
)
from services.assistant_tools import run_tool as run_read_tool
from services.assistant_tools_schema import WRITE_INTENTS
from services.clinic_agent_tools import ToolNotAllowed, ToolPermissionDenied, run_tool as run_write_tool
from services.clinic_agent_tools_schema import lookup_tool

logger = logging.getLogger("clinic_agent")

READ_TOOL_ALIASES = {
    "get_rdv_count_today",
    "get_next_rdv",
    "list_rd_today",
    "list_inactive_patients",
    "get_stock_overview",
    "get_revenue_summary",
    "send_daily_report",
}


def _extract_between(text: str, start: str, end: Optional[str] = None) -> str:
    lower = text.lower()
    s = lower.find(start)
    if s == -1:
        return ""
    s += len(start)
    if end:
        e = lower.find(end, s)
        if e != -1:
            return text[s:e].strip()
    return text[s:].strip()


def _classify(question: str) -> tuple[str, dict[str, Any]]:
    text = (question or "").strip()
    lower = text.lower()

    m = re.search(r"(?:recherche|chercher|trouve?r?)\s+(?:le\s+)?patient\s+(.+)$", lower)
    if m:
        return "search_patient", {"query": text[m.start(1):].strip()}

    m = re.search(r"(?:contacte|écris|ecris)\s+(?:le\s+)?patient\s+(\d+)$", lower)
    if m:
        return "compose_whatsapp_for_patient", {"patient_id": int(m.group(1))}

    m = re.search(r"(?:crée|cree|ajoute)\s+rdv\s+patient\s+(\d+)\s+praticien\s+(\d+)\s+acte\s+(\d+)\s+le\s+([0-9t:\-]+)(?:\s+salle\s+(.+))?$", lower)
    if m:
        return "create_rdv", {
            "patient_id": int(m.group(1)),
            "praticien_id": int(m.group(2)),
            "acte_id": int(m.group(3)),
            "date_heure": m.group(4),
            "salle": m.group(5).strip() if m.group(5) else None,
        }

    m = re.search(r"(?:modifier|reprogrammer|déplacer|deplacer)\s+rdv\s+(\d+)(?:\s+au\s+([0-9t:\-]+))?(?:\s+statut\s+(\w+))?", lower)
    if m:
        params: dict[str, Any] = {"rdv_id": int(m.group(1))}
        if m.group(2):
            params["date_heure"] = m.group(2)
        if m.group(3):
            params["statut"] = m.group(3)
        return "update_rdv", params

    m = re.search(r"(?:annule|annuler|supprime)\s+rdv\s+(\d+)(?:\s+raison\s+(.+))?$", lower)
    if m:
        return "cancel_rdv", {"rdv_id": int(m.group(1)), "raison": m.group(2).strip() if m.group(2) else "Annulé via agent"}

    m = re.search(r"(?:envoie|envoye|envoi)\s+whatsapp\s+patient\s+(\d+)\s*[:\-]\s*(.+)$", lower)
    if m:
        start = text.lower().find(m.group(2))
        return "send_whatsapp", {"patient_id": int(m.group(1)), "message": text[start:].strip()}

    m = re.search(r"(?:envoie|envoye|envoi)\s+email\s+patient\s+(\d+)", lower)
    if m:
        subject = _extract_between(text, "sujet:", "message:") or _extract_between(text, "subject:", "message:")
        message = _extract_between(text, "message:")
        if subject and message:
            return "send_email", {"patient_id": int(m.group(1)), "subject": subject, "message": message}

    m = re.search(r"(?:lance|lancer|crée|cree)\s+campagne", lower)
    if m:
        nom = _extract_between(text, "nom:", "type:") or "Campagne IA"
        type_ = _extract_between(text, "type:", "message:") or "whatsapp"
        message = _extract_between(text, "message:")
        segment = _extract_between(text, "segment:", "message:")
        if message:
            return "launch_campaign", {
                "nom": nom,
                "type": type_.strip().lower(),
                "message_template": message,
                "segment_label": segment or "non_precise",
            }

    m = re.search(r"(?:crée|cree|ajoute)\s+t(?:â|a)che\s*[:\-]?\s*(.+)$", lower)
    if m:
        titre = text[m.start(1):].strip()
        return "create_internal_task", {"titre": titre}

    if "résumé de la journée" in lower or "resume de la journee" in lower:
        return "summarize_day", {}

    if "statistique" in lower or "ca semaine" in lower or "ca mois" in lower:
        return "get_statistics", {"periode": "mois" if "mois" in lower else "semaine"}

    # Repli lecture seule bloc 2
    if any(x in lower for x in ["rdv", "rendez-vous", "patient", "stock", "botox", "chiffre d'affaires", "rapport du jour"]):
        from services.assistant_ia import _detect_intent  # import local pour éviter boucle lourde
        return _detect_intent(question)

    return "unknown", {}


def _humanize(tool_name: str, payload: dict[str, Any], lang: str = "fr") -> str:
    if lang == "darija":
        if tool_name == "search_patient":
            items = payload.get("items") or []
            if not items:
                return "ما لقيتش حريف."
            lines = [f"- #{p['id']} {p['prenom']} {p['nom']} — {p.get('telephone', '')}" for p in items[:5]]
            return "الحرفاء اللي لقيت :\n" + "\n".join(lines)
        if tool_name == "create_rdv":
            return f"تعمل الموعد #{payload['id']} نهار {payload['date_heure']}."
        if tool_name == "update_rdv":
            return f"تبدل الموعد #{payload['id']}."
        if tool_name == "cancel_rdv":
            return f"تلغى الموعد #{payload['id']}."
        if tool_name == "send_whatsapp":
            return f"الرسالة تبعثت للحريف #{payload['patient_id']}."
        if tool_name == "send_email":
            return f"الإيمايل تعالج للحريف #{payload['patient_id']} — الحالة : {payload.get('statut')}."
        if tool_name == "launch_campaign":
            return f"الحملة #{payload['id']} تعملت، الحالة : {payload['statut']}."
        if tool_name == "get_statistics":
            return f"رقم الأعمال {payload.get('periode')} : {payload.get('ca_ttc', 0):.3f} دينار."
        if tool_name == "create_internal_task":
            return f"المهمة #{payload['id']} تعملت : {payload['titre']}."
        if tool_name == "summarize_day":
            return (
                f"ملخص النهار — المواعيد : {payload.get('rdvs_aujourdhui', 0)} — "
                f"رقم الأعمال الجمعة : {payload.get('ca_semaine', {}).get('ca_ttc', 0):.3f} دينار."
            )
        return json.dumps(payload, ensure_ascii=False)

    if tool_name == "search_patient":
        items = payload.get("items") or []
        if not items:
            return "Aucun patient trouvé."
        lines = [f"- #{p['id']} {p['prenom']} {p['nom']} — {p.get('telephone', '')}" for p in items[:5]]
        return "Patients trouvés :\n" + "\n".join(lines)
    if tool_name == "create_rdv":
        return f"RDV créé #{payload['id']} pour le {payload['date_heure']}."
    if tool_name == "update_rdv":
        return f"RDV #{payload['id']} mis à jour."
    if tool_name == "cancel_rdv":
        return f"RDV #{payload['id']} annulé."
    if tool_name == "send_whatsapp":
        return f"WhatsApp envoyé au patient #{payload['patient_id']}."
    if tool_name == "send_email":
        return f"Email traité pour le patient #{payload['patient_id']} — statut : {payload.get('statut')}."
    if tool_name == "launch_campaign":
        return f"Campagne #{payload['id']} créée en statut {payload['statut']}."
    if tool_name == "get_statistics":
        return f"CA {payload.get('periode')} : {payload.get('ca_ttc', 0):.3f} DT."
    if tool_name == "create_internal_task":
        return f"Tâche #{payload['id']} créée : {payload['titre']}."
    if tool_name == "summarize_day":
        return (
            f"Résumé du jour — RDV : {payload.get('rdvs_aujourdhui', 0)} — "
            f"CA semaine : {payload.get('ca_semaine', {}).get('ca_ttc', 0):.3f} DT."
        )
    return json.dumps(payload, ensure_ascii=False)


async def _execute_tool(tool_name: str, params: dict[str, Any], current_user: dict[str, Any], db: AsyncSession, lang: str = "fr") -> tuple[dict[str, Any], str]:
    if tool_name in READ_TOOL_ALIASES:
        payload = await run_read_tool(tool_name, params, current_user, db)
    else:
        payload = await run_write_tool(tool_name, params, current_user, db)
    return payload, _humanize(tool_name, payload, lang)


async def handle_agent_message(numero: str, question: str, current_user: dict[str, Any], db: AsyncSession) -> dict[str, Any]:
    session = await get_or_create_session(numero, current_user, db)

    # Bloc 7 : une demande clinique à risque est escaladée avant tout tool,
    # toute confirmation et toute action métier.
    lang = _detect_lang(question)
    if is_medical_escalation(question):
        refusal = escalation_message(lang)
        commande = await log_assistant_command(
            db, session=session, current_user=current_user, numero=numero,
            type_commande=TypeCommandeAssistantEnum.HORS_PERIMETRE.value,
            question=question, statut="escalade", reponse=refusal,
            raison_refus="Demande médicale nécessitant un praticien",
            contexte={"medical_level": "ESCALADE", "original_message": question},
        )
        return {"reponse": refusal, "commande_id": commande.id, "statut": "escalade", "niveau": "ESCALADE"}

    # 1) confirmation en attente
    confirmed_details, confirmation_message = await consume_confirmation_if_valid(
        question, session=session, current_user=current_user, db=db
    )
    if confirmation_message:
        commande = await log_assistant_command(
            db,
            session=session,
            current_user=current_user,
            numero=numero,
            type_commande=TypeCommandeAssistantEnum.ECRITURE_AGENT.value,
            question=question,
            statut="confirmation_en_attente",
            reponse=confirmation_message,
        )
        return {"reponse": confirmation_message, "commande_id": commande.id, "statut": "confirmation_en_attente"}
    if confirmed_details:
        tool_name = confirmed_details.get("tool_name")
        params = confirmed_details.get("tool_args") or {}
        lang = confirmed_details.get("lang", "fr")
        try:
            payload, reponse = await _execute_tool(tool_name, params, current_user, db, lang)
            await set_session_context(session, db, None)
            commande = await log_assistant_command(
                db,
                session=session,
                current_user=current_user,
                numero=numero,
                type_commande=TypeCommandeAssistantEnum.ECRITURE_AGENT.value,
                question=question,
                statut="ok",
                reponse=reponse,
                intent_detecte=tool_name,
                outil_appele=tool_name,
                parametres=params,
                tool_payload=payload,
                contexte={"confirmed": True},
            )
            return {"reponse": reponse, "commande_id": commande.id, "tool_payload": payload, "statut": "ok"}
        except ToolPermissionDenied as e:
            refus_msg = "الوصول ممنوع، ما عندكش الصلاحية." if lang == "darija" else "Accès refusé par la matrice RBAC."
            commande = await log_assistant_command(
                db,
                session=session,
                current_user=current_user,
                numero=numero,
                type_commande=TypeCommandeAssistantEnum.ECRITURE_AGENT.value,
                question=question,
                statut="erreur",
                reponse=refus_msg,
                intent_detecte=tool_name,
                outil_appele=tool_name,
                parametres=params,
                erreur_message=str(e),
                contexte={"confirmed": True},
            )
            return {"reponse": refus_msg, "commande_id": commande.id, "statut": "erreur"}
        except Exception as e:
            echec_msg = "الطلب المؤكد فشل." if lang == "darija" else "L'action confirmée a échoué."
            commande = await log_assistant_command(
                db,
                session=session,
                current_user=current_user,
                numero=numero,
                type_commande=TypeCommandeAssistantEnum.ECRITURE_AGENT.value,
                question=question,
                statut="erreur",
                reponse=echec_msg,
                intent_detecte=tool_name,
                outil_appele=tool_name,
                parametres=params,
                erreur_message=str(e),
                contexte={"confirmed": True},
            )
            logger.exception("Execution confirmée en échec: %s", e)
            return {"reponse": echec_msg, "commande_id": commande.id, "statut": "erreur"}

    # 2) contexte multi-tour : composer un WhatsApp après "contacte patient X"
    context = await get_session_context(session)
    if context and context.get("flow") == "compose_whatsapp" and context.get("patient_id"):
        lang = _detect_lang(question)
        tool_name = "send_whatsapp"
        params = {"patient_id": int(context["patient_id"]), "message": question.strip()}
        confirmation = await create_confirmation(
            db,
            session=session,
            current_user=current_user,
            numero=numero,
            tool_name=tool_name,
            tool_args=params,
            summary=f"Envoyer un WhatsApp au patient #{context['patient_id']}",
            resource_type="patient",
            resource_id=int(context["patient_id"]),
            lang=lang,
        )
        await set_session_context(session, db, None)
        text = (f"لازم تأكيد. اكتب CONFIRMER {confirmation.code_confirmation} باش نبعث الرسالة للحريف #{context['patient_id']}, ولا NON باش تلغي."
                if lang == "darija" else
                f"Confirmation obligatoire. Répondez CONFIRMER {confirmation.code_confirmation} pour envoyer ce message au patient #{context['patient_id']}, ou NON pour annuler.")
        commande = await log_assistant_command(
            db,
            session=session,
            current_user=current_user,
            numero=numero,
            type_commande=TypeCommandeAssistantEnum.ECRITURE_AGENT.value,
            question=question,
            statut="confirmation_en_attente",
            reponse=text,
            intent_detecte=tool_name,
            outil_appele=tool_name,
            parametres=params,
            contexte={"multi_turn": True},
        )
        return {"reponse": text, "commande_id": commande.id, "statut": "confirmation_en_attente"}

    # 3) classifier l'intention
    lang = _detect_lang(question)
    tool_name, params = _classify(question)
    if tool_name == "compose_whatsapp_for_patient":
        await set_session_context(session, db, {"flow": "compose_whatsapp", "patient_id": params["patient_id"]})
        text = (f"شنوة الرسالة اللي تحب تبعثها للحريف #{params['patient_id']} ؟"
                if lang == "darija" else
                f"Quel message voulez-vous envoyer au patient #{params['patient_id']} ?")
        commande = await log_assistant_command(
            db,
            session=session,
            current_user=current_user,
            numero=numero,
            type_commande=TypeCommandeAssistantEnum.ECRITURE_AGENT.value,
            question=question,
            statut="en_attente",
            reponse=text,
            intent_detecte=tool_name,
            contexte={"multi_turn": True},
        )
        return {"reponse": text, "commande_id": commande.id, "statut": "en_attente"}

    if tool_name == "unknown":
        text = ("ما فهمتش. أمثلة : دور على حريف أحمد، الغي موعد 12 السبب غياب، ابعث واتساب للحريف 3: أهلا."
                 if lang == "darija" else
                 "Je n'ai pas compris. Exemples : recherche patient Ahmed, annule RDV 12 raison absence, envoie WhatsApp patient 3: Bonjour.")
        commande = await log_assistant_command(
            db,
            session=session,
            current_user=current_user,
            numero=numero,
            type_commande=TypeCommandeAssistantEnum.HORS_PERIMETRE.value,
            question=question,
            statut="refuse",
            reponse=text,
            intent_detecte="unknown",
            raison_refus="Intent inconnu",
        )
        return {"reponse": text, "commande_id": commande.id, "statut": "refuse"}

    if tool_name in WRITE_INTENTS:
        # compatibilité avec les anciens noms de refus bloc 2
        text = ("هالطلب يحتاج الصيغة الكاملة (بلوك 4). عاود صيغه بطريقة مدعومة."
                if lang == "darija" else
                "Cette action nécessite l'agent Bloc 4 structuré. Reformulez avec le format supporté.")
        commande = await log_assistant_command(
            db,
            session=session,
            current_user=current_user,
            numero=numero,
            type_commande=TypeCommandeAssistantEnum.HORS_PERIMETRE.value,
            question=question,
            statut="refuse",
            reponse=text,
            intent_detecte=tool_name,
            raison_refus="Nom d'intent hérité non exécutable",
        )
        return {"reponse": text, "commande_id": commande.id, "statut": "refuse"}

    # 4) Confirmation obligatoire pour outils sensibles
    spec = lookup_tool(tool_name)
    if spec and spec.get("sensitive"):
        confirmation = await create_confirmation(
            db,
            session=session,
            current_user=current_user,
            numero=numero,
            tool_name=tool_name,
            tool_args=params,
            summary=tool_name,
            resource_type="agent_tool",
            resource_id=None,
            lang=lang,
        )
        text = (f"لازم تأكيد. اكتب CONFIRMER {confirmation.code_confirmation} باش تفعل {tool_name}, ولا NON باش تلغي."
                if lang == "darija" else
                f"Confirmation obligatoire. Répondez CONFIRMER {confirmation.code_confirmation} pour valider {tool_name}, ou NON pour annuler.")
        commande = await log_assistant_command(
            db,
            session=session,
            current_user=current_user,
            numero=numero,
            type_commande=TypeCommandeAssistantEnum.ECRITURE_AGENT.value,
            question=question,
            statut="confirmation_en_attente",
            reponse=text,
            intent_detecte=tool_name,
            outil_appele=tool_name,
            parametres=params,
        )
        return {"reponse": text, "commande_id": commande.id, "statut": "confirmation_en_attente"}

    # 5) Exécution directe
    try:
        payload, reponse = await _execute_tool(tool_name, params, current_user, db, lang)
        commande = await log_assistant_command(
            db,
            session=session,
            current_user=current_user,
            numero=numero,
            type_commande=(TypeCommandeAssistantEnum.CONSULTER_INFOS_CLINIQUE.value if tool_name in READ_TOOL_ALIASES else TypeCommandeAssistantEnum.ECRITURE_AGENT.value),
            question=question,
            statut="ok",
            reponse=reponse,
            intent_detecte=tool_name,
            outil_appele=tool_name,
            parametres=params,
            tool_payload=payload,
        )
        return {"reponse": reponse, "commande_id": commande.id, "tool_payload": payload, "statut": "ok"}
    except ToolPermissionDenied as e:
        refus_msg2 = "الوصول ممنوع، ما عندكش الصلاحية." if lang == "darija" else "Accès refusé par la matrice RBAC."
        commande = await log_assistant_command(
            db,
            session=session,
            current_user=current_user,
            numero=numero,
            type_commande=TypeCommandeAssistantEnum.ECRITURE_AGENT.value,
            question=question,
            statut="erreur",
            reponse=refus_msg2,
            intent_detecte=tool_name,
            outil_appele=tool_name,
            parametres=params,
            erreur_message=str(e),
        )
        return {"reponse": refus_msg2, "commande_id": commande.id, "statut": "erreur"}
    except ToolNotAllowed as e:
        indispo_msg = "الأداة موش متوفرة." if lang == "darija" else "Outil indisponible."
        commande = await log_assistant_command(
            db,
            session=session,
            current_user=current_user,
            numero=numero,
            type_commande=TypeCommandeAssistantEnum.ECRITURE_AGENT.value,
            question=question,
            statut="erreur",
            reponse=indispo_msg,
            intent_detecte=tool_name,
            parametres=params,
            erreur_message=str(e),
        )
        return {"reponse": indispo_msg, "commande_id": commande.id, "statut": "erreur"}
    except Exception as e:
        logger.exception("Agent Bloc 4 en échec: %s", e)
        erreur_msg = "صار مشكل داخلي." if lang == "darija" else "Une erreur interne est survenue."
        commande = await log_assistant_command(
            db,
            session=session,
            current_user=current_user,
            numero=numero,
            type_commande=TypeCommandeAssistantEnum.ECRITURE_AGENT.value,
            question=question,
            statut="erreur",
            reponse=erreur_msg,
            intent_detecte=tool_name,
            outil_appele=tool_name,
            parametres=params,
            erreur_message=str(e),
        )
        return {"reponse": erreur_msg, "commande_id": commande.id, "statut": "erreur"}
