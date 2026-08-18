"""
AutoCommerce Clinic — Service Copilote CRM (Bloc 7) — v2 (LLM réel)

Depuis n'importe quelle fiche patient, l'assistant :
- Résume le dossier (LLM)
- Suggère un traitement (LLM)
- Détecte les patients à risque (SQL + LLM)
- Génère un compte rendu médical (LLM)
- Prépare le prochain rendez-vous (LLM + tools)
- Génère un brouillon WhatsApp / email (LLM, **jamais** envoyé sans validation)

Compatibilité ascendante : toutes les méthodes existantes sont conservées ;
elles sont **enrichies** par un appel LLM optionnel, sans dépendance dure.
Si LLM indisponible, fallback SQL/chiffres + champ ``llm_status``.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
from typing import Any, Dict

from sqlalchemy import select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from models.database import (
    Patient, DossierMedical, StatutRDV, SeriePhotos,
)

from core.llm_client import LLMClient, LLMUnavailable, get_llm_client, pseudonymize_pii
from core.prompt_templates import (
    COPILOTE_SUMMARY, COPILOTE_WHATSAPP_DRAFT,
)

logger = logging.getLogger("copilote_crm")


def _llm_status_marker(outcome: Any) -> str:
    """Marqueur honnête du statut LLM dans la sortie JSON."""
    if isinstance(outcome, LLMUnavailable):
        return f"unavailable:{outcome.provider}:{outcome.reason[:120]}"
    return "ok"


class CopiloteCRMService:
    """Service d'assistance CRM pour les fiches patients — enrichi LLM."""

    # ── helpers ─────────────────────────────────────────────────

    @staticmethod
    async def _load_patient_full(session: AsyncSession, patient_id: int):
        stmt = select(Patient).where(Patient.id == patient_id).options(
            selectinload(Patient.dossiers).selectinload(DossierMedical.acte),
            selectinload(Patient.rdvs),
            selectinload(Patient.factures),
            selectinload(Patient.series_photos).selectinload(SeriePhotos.photos),
            selectinload(Patient.fidelite_transactions),
        )
        return (await session.execute(stmt)).scalar_one_or_none()

    @staticmethod
    def _patient_to_dict(p: Patient) -> Dict[str, Any]:
        return {
            "id": p.id,
            "prenom": getattr(p, "prenom", ""),
            "nom": getattr(p, "nom", ""),
            "email": getattr(p, "email", None),
            "telephone": getattr(p, "telephone", None),
            "date_naissance": getattr(p, "date_naissance", None),
            "niveau_fidelite": getattr(getattr(p, "niveau_fidelite", None), "value", None),
            "notes": getattr(p, "notes", None),
        }



    # ── API publique ─────────────────────────────────────────────

    @staticmethod
    async def summarize_patient_file(
        session: AsyncSession, patient_id: int,
        settings: Any = None, llm: LLMClient = None,
    ) -> Dict[str, Any]:
        """
        Résumer le dossier patient : historique, actes, photos, satisfaction.
        Retourne un dict avec ``llm_summary`` (texte LLM) + ``data`` (chiffres).
        """
        patient = await CopiloteCRMService._load_patient_full(session, patient_id)
        if not patient:
            return {"error": "Patient not found", "patient_id": patient_id}

        # ── chiffres (toujours disponibles) ──
        actes_summary: Dict[str, Dict[str, Any]] = {}
        for d in patient.dossiers:
            if not d.acte:
                continue
            name = d.acte.nom
            slot = actes_summary.setdefault(name, {
                "count": 0, "last_date": None, "satisfaction_scores": [],
            })
            slot["count"] += 1
            slot["last_date"] = d.date_acte.isoformat()
            if d.satisfaction_patient is not None:
                slot["satisfaction_scores"].append(d.satisfaction_patient)
        for v in actes_summary.values():
            scores = v.pop("satisfaction_scores", [])
            v["avg_satisfaction"] = round(sum(scores) / len(scores), 1) if scores else None

        rdvs = patient.rdvs or []
        rdvs_total = len(rdvs)
        rdvs_done = sum(1 for r in rdvs if r.statut == StatutRDV.TERMINE.value)
        rdvs_cancel = sum(1 for r in rdvs if r.statut == StatutRDV.ANNULE.value)
        rdvs_noshow = sum(1 for r in rdvs if r.statut == StatutRDV.NO_SHOW.value)
        next_rdv = None
        now = datetime.utcnow()
        future = sorted(
            (r for r in rdvs if r.date_heure_debut and r.date_heure_debut > now
             and r.statut not in (StatutRDV.ANNULE.value,)),
            key=lambda r: r.date_heure_debut,
        )
        if future:
            r0 = future[0]
            next_rdv = {
                "id": r0.id,
                "date": r0.date_heure_debut.isoformat(),
                "acte": r0.acte.nom if r0.acte else None,
                "praticien": (f"{r0.praticien.prenom} {r0.praticien.nom}"
                              if getattr(r0, "praticien", None) else None),
            }

        data_payload = {
            "patient": CopiloteCRMService._patient_to_dict(patient),
            "actes_summary": actes_summary,
            "rdvs": {
                "total": rdvs_total,
                "completed": rdvs_done,
                "cancelled": rdvs_cancel,
                "no_show": rdvs_noshow,
                "next": next_rdv,
            },
            "factures": {
                "count": len(getattr(patient, "factures", []) or []),
            },
            "photos": {
                "series_count": len(getattr(patient, "series_photos", []) or []),
            },
        }

        result: Dict[str, Any] = {
            "patient_id": patient_id,
            "data": data_payload,
            "llm_summary": None,
            "llm_status": "skipped",
        }

        # ── appel LLM optionnel ──
        if llm is None and settings is not None:
            llm = get_llm_client(settings)
        if llm is None:
            return result

        try:
            # Pseudonymisation avant envoi au LLM
            patient_safe = pseudonymize_pii(data_payload["patient"])
            
            msgs = COPILOTE_SUMMARY.render(
                patient_json=json.dumps(patient_safe, ensure_ascii=False, default=str),
                dossiers_json=json.dumps(actes_summary, ensure_ascii=False, default=str),
                rdvs_json=json.dumps(data_payload["rdvs"], ensure_ascii=False, default=str),
                factures_json=json.dumps(data_payload["factures"], ensure_ascii=False, default=str),
                photos_json=json.dumps(data_payload["photos"], ensure_ascii=False, default=str),
            )
            out = await llm.chat(
                msgs,
                max_tokens=600,
                budget_subject=f"clinic:{patient.clinic_id}:copilote_summary",
                budget_clinic_id=patient.clinic_id,
            )
            if isinstance(out, LLMUnavailable):
                result["llm_status"] = _llm_status_marker(out)
            else:
                result["llm_summary"] = out.text
                result["llm_status"] = "ok"
                result["llm_provider"] = out.provider
                result["llm_latency_ms"] = out.latency_ms
        except Exception as exc:
            logger.exception("copilote_summarize_llm_error patient=%s", patient_id)
            result["llm_status"] = f"exception:{exc!r}"

        return result

    @staticmethod
    async def suggest_treatment(
        session: AsyncSession, patient_id: int,
        settings: Any = None, llm: LLMClient = None,
    ) -> Dict[str, Any]:
        patient = await CopiloteCRMService._load_patient_full(session, patient_id)
        if not patient:
            return {"error": "Patient not found", "patient_id": patient_id}
        summary = await CopiloteCRMService.summarize_patient_file(session, patient_id, settings, llm)
        suggestion = {
            "patient_id": patient_id,
            "data": summary.get("data"),
            "recommendation_short": (
                "Reprendre la consultation : vérifiez l'historique des actes "
                "récents et la satisfaction avant de proposer un nouveau soin."
            ),
            "llm_status": summary.get("llm_status"),
        }
        if llm is None and settings is not None:
            llm = get_llm_client(settings)
        if llm is None:
            return suggestion
        try:
            from core.prompt_templates import COPILOTE_WHATSAPP_DRAFT  # noqa
            system = (
                "Tu es médecin-conseil. À partir du dossier patient JSON, propose "
                "1 soin adapté. Justification en 3 phrases maximum."
            )
            # Pseudonymisation du dossier complet
            data_safe = pseudonymize_pii(summary.get("data", {}))
            
            user = f"Dossier :\n{json.dumps(data_safe, ensure_ascii=False, default=str)[:3000]}"
            out = await llm.chat(
                [{"role": "system", "content": system}, {"role": "user", "content": user}],
                max_tokens=400,
                budget_subject=f"clinic:{patient.clinic_id}:copilote_treatment",
                budget_clinic_id=patient.clinic_id,
            )
            if isinstance(out, LLMUnavailable):
                suggestion["llm_status"] = _llm_status_marker(out)
            else:
                suggestion["recommendation"] = out.text
                suggestion["llm_status"] = "ok"
                suggestion["llm_provider"] = out.provider
        except Exception as exc:
            logger.exception("copilote_suggest_treatment_llm_error")
            suggestion["llm_status"] = f"exception:{exc!r}"
        return suggestion

    @staticmethod
    async def detect_at_risk_patients(
        session: AsyncSession, clinic_id: int = 1,
        settings: Any = None, llm: LLMClient = None,
    ) -> Dict[str, Any]:
        """Liste brute en SQL + résumé LLM si dispo."""
        cutoff = datetime.utcnow() - timedelta(days=120)
        stmt = select(Patient).where(
            and_(
                Patient.clinic_id == clinic_id,
                or_(
                    Patient.derniere_visite == None,  # noqa: E711
                    Patient.derniere_visite < cutoff,
                ),
            )
        ).limit(50)
        patients = (await session.execute(stmt)).scalars().all()
        items = [{
            "id": p.id,
            "name": f"{getattr(p, 'prenom', '')} {getattr(p, 'nom', '')}".strip(),
            "last_visit": getattr(p, "derniere_visite", None),
            "phone": getattr(p, "telephone", None),
        } for p in patients]
        result: Dict[str, Any] = {
            "clinic_id": clinic_id,
            "at_risk_count": len(items),
            "items": items,
            "llm_commentary": None,
            "llm_status": "skipped",
        }
        if llm is None and settings is not None:
            llm = get_llm_client(settings)
        if llm is None or not items:
            return result
        try:
            # Pseudonymisation de la liste pour le prompt
            items_safe = pseudonymize_pii(items)

            msgs = [
                {"role": "system", "content": (
                    "Tu es le directeur d'une clinique. Tu reçois une liste de patients "
                    "à risque de churn. Donne 2-3 phrases de commentaire + 1 action prioritaire."
                )},
                {"role": "user", "content": (
                    f"Patients ({len(items)}) :\n" + json.dumps(items_safe, ensure_ascii=False, default=str)[:3000]
                )},
            ]
            out = await llm.chat(
                msgs,
                max_tokens=400,
                budget_subject=f"clinic:{clinic_id}:copilote_at_risk",
                budget_clinic_id=clinic_id,
            )
            if isinstance(out, LLMUnavailable):
                result["llm_status"] = _llm_status_marker(out)
            else:
                result["llm_commentary"] = out.text
                result["llm_status"] = "ok"
                result["llm_provider"] = out.provider
        except Exception as exc:
            logger.exception("copilote_at_risk_llm_error")
            result["llm_status"] = f"exception:{exc!r}"
        return result

    @staticmethod
    async def generate_medical_report(
        session: AsyncSession, patient_id: int,
        settings: Any = None, llm: LLMClient = None,
    ) -> Dict[str, Any]:
        summary = await CopiloteCRMService.summarize_patient_file(session, patient_id, settings, llm)
        if "error" in summary:
            return summary
        result = {
            "patient_id": patient_id,
            "draft_sections": {
                "motif_consultation": "À compléter par le praticien.",
                "historique": "Voir dossier patient complet.",
                "examen_clinique": "À compléter.",
                "conclusion": (summary.get("llm_summary")
                              or "Conclusion libre — dossier en récapitulatif automatique."),
                "recommandations": "Suivi selon protocole interne.",
            },
            "llm_status": summary.get("llm_status"),
        }
        return result

    @staticmethod
    async def prepare_next_appointment(
        session: AsyncSession, patient_id: int,
        settings: Any = None, llm: LLMClient = None,
    ) -> Dict[str, Any]:
        summary = await CopiloteCRMService.summarize_patient_file(session, patient_id, settings, llm)
        if "error" in summary:
            return summary
        next_rdv = (summary.get("data") or {}).get("rdvs", {}).get("next")
        return {
            "patient_id": patient_id,
            "next_rdv": next_rdv,
            "checklist": {
                "confirmation_telephone_ok": False,
                "consentements_a_jour": False,
                "photos_avant_a_jour": False,
                "facturation_n_1_ok": False,
            },
            "llm_status": summary.get("llm_status"),
        }

    @staticmethod
    async def generate_whatsapp_draft(
        session: AsyncSession, patient_id: int,
        message_type: str = "appointment_reminder",
        settings: Any = None, llm: LLMClient = None,
    ) -> Dict[str, Any]:
        """Brouillon **jamais envoyé** sans validation humaine explicite."""
        patient = await CopiloteCRMService._load_patient_full(session, patient_id)
        if not patient:
            return {"error": "Patient not found", "patient_id": patient_id}

        templates = {
            "appointment_reminder": {
                "subject": "Confirmation de votre rendez-vous",
                "body": (
                    "Bonjour {patient_name}, votre prochain RDV est prévu le "
                    "{next_rdv_date}. Merci de confirmer votre présence."
                ),
            },
            "followup": {
                "subject": "Suivi de votre traitement",
                "body": (
                    "Bonjour {patient_name}, nous espérons que vous allez bien "
                    "suite à votre dernier passage à la clinique."
                ),
            },
            "birthday": {
                "subject": "Joyeux anniversaire !",
                "body": (
                    "Bonjour {patient_name}, toute l'équipe de la {clinic_name} "
                    "vous souhaite un très joyeux anniversaire 🎉."
                ),
            },
        }
        base = templates.get(message_type, templates["appointment_reminder"])
        next_rdv_date = ""
        future = sorted(
            (r for r in (patient.rdvs or [])
             if r.date_heure_debut and r.date_heure_debut > datetime.utcnow()
             and r.statut not in (StatutRDV.ANNULE.value,)),
            key=lambda r: r.date_heure_debut,
        )
        if future:
            next_rdv_date = future[0].date_heure_debut.strftime("%d/%m/%Y à %Hh%M")

        prelim = {
            "patient_id": patient.id,
            "patient_name": f"{getattr(patient, 'prenom', '')} {getattr(patient, 'nom', '')}".strip(),
            "patient_phone": getattr(patient, "telephone", None),
            "message_type": message_type,
            "subject": base["subject"],
            "body": base["body"].format(
                patient_name=f"{getattr(patient, 'prenom', '')}",
                next_rdv_date=next_rdv_date,
                clinic_name="Clinique",
            ),
            "requires_validation": True,
            "validation_note": (
                "Brouillon — JAMAIS envoyé automatiquement ; "
                "validation humaine obligatoire via /assistant/commandes/{id}/approve."
            ),
            "llm_status": "skipped",
        }

        if llm is None and settings is not None:
            llm = get_llm_client(settings)
        if llm is None:
            return prelim
        try:
            msgs = COPILOTE_WHATSAPP_DRAFT.render(
                message_type=message_type,
                context_json=json.dumps({
                    "patient_phone": prelim["patient_phone"],
                    "patient_name": prelim["patient_name"],
                    "next_rdv_date": next_rdv_date,
                }, ensure_ascii=False),
                patient_name=prelim["patient_name"],
                next_rdv_date=next_rdv_date or "non planifié",
                clinic_name="Clinique",
            )
            out = await llm.chat(
                msgs,
                max_tokens=300,
                response_format_json=True,
                budget_subject=f"clinic:{patient.clinic_id}:copilote_whatsapp_draft",
                budget_clinic_id=patient.clinic_id,
            )
            if isinstance(out, LLMUnavailable):
                prelim["llm_status"] = _llm_status_marker(out)
            else:
                try:
                    parsed = json.loads(out.text)
                    if isinstance(parsed.get("subject"), str):
                        prelim["subject"] = parsed["subject"][:120]
                    if isinstance(parsed.get("body"), str):
                        prelim["body"] = parsed["body"][:800]
                except json.JSONDecodeError:
                    # LLM a renvoyé du texte brut → on le conserve en corps
                    prelim["body"] = out.text[:800]
                prelim["llm_status"] = "ok"
                prelim["llm_provider"] = out.provider
        except Exception as exc:
            logger.exception("whatsapp_draft_llm_error")
            prelim["llm_status"] = f"exception:{exc!r}"
        return prelim

    @staticmethod
    async def generate_email_draft(
        session: AsyncSession, patient_id: int,
        email_type: str = "appointment_reminder",
        settings: Any = None, llm: LLMClient = None,
    ) -> Dict[str, Any]:
        """Même logique que ``generate_whatsapp_draft`` mais format email."""
        # Réutilisation pragmatique — l'objectif est un brouillon éditable
        draft = await CopiloteCRMService.generate_whatsapp_draft(
            session, patient_id, message_type=email_type, settings=settings, llm=llm,
        )
        if "error" in draft:
            return draft
        draft["email_type"] = email_type
        draft["channel"] = "email"
        return draft
