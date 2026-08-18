"""
AutoCommerce Clinic — Service Dashboard IA (Bloc 5) — v2 (LLM réel)

- Lecture seule, agrégation SQL pour les chiffres ;
- Narration LLM du résumé de journée (Bloc 5 "résumé humain") ;
- AI recommendations + revenue forecast **enrichis** par LLM si dispo ;
- Mode dégradé honnête : retour du SQL + champs ``llm_*``.

Compatibilité ascendante : aucune signature supprimée.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, date, timedelta
from decimal import Decimal
from typing import Any, Dict

from sqlalchemy import select, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from models.database import (
    RendezVous, Patient, Facture, Utilisateur, DossierMedical,
    NiveauFidelite, StatutRDV,
    StatutFacture, ProduitInjectable,
)

from core.llm_client import LLMClient, LLMUnavailable, get_llm_client, pseudonymize_pii
from core.prompt_templates import DASHBOARD_NARRATION

logger = logging.getLogger("dashboard_ia")


def _status_marker(outcome: Any) -> str:
    if isinstance(outcome, LLMUnavailable):
        return f"unavailable:{outcome.provider}:{outcome.reason[:120]}"
    return "ok"


class DashboardIAService:
    """Service de Dashboard IA — Lecture seule, enrichi LLM."""

    # ── helpers ─────────────────────────────────────────────────

    @staticmethod
    async def _raw_daily_metrics(
        session: AsyncSession, clinic_id: int, day: date,
    ) -> Dict[str, Any]:
        today = day
        tomorrow = today + timedelta(days=1)
        today_start = datetime.combine(today, datetime.min.time())
        today_end = datetime.combine(today, datetime.max.time())
        tomorrow_start = datetime.combine(tomorrow, datetime.min.time())
        tomorrow_end = datetime.combine(tomorrow, datetime.max.time())

        rdvs = (await session.execute(
            select(RendezVous).where(and_(
                RendezVous.clinic_id == clinic_id,
                RendezVous.date_heure_debut >= today_start,
                RendezVous.date_heure_debut <= today_end,
            )).options(
                selectinload(RendezVous.patient),
                selectinload(RendezVous.praticien),
                selectinload(RendezVous.acte),
            )
        )).scalars().all()
        revenue_today = (await session.execute(
            select(func.sum(Facture.total_ttc)).where(and_(
                Facture.clinic_id == clinic_id,
                Facture.date_emission == today,
                Facture.statut.in_([
                    StatutFacture.PAYEE.value,
                    StatutFacture.PARTIELLEMENT_PAYEE.value,
                ]),
            ))
        )).scalar() or Decimal("0.000")
        unpaid = (await session.execute(
            select(func.count(Facture.id)).where(and_(
                Facture.clinic_id == clinic_id,
                Facture.statut.in_([
                    StatutFacture.ENVOYEE.value, StatutFacture.BROUILLON.value,
                ]),
            ))
        )).scalar() or 0
        rdv_tom = (await session.execute(
            select(func.count(RendezVous.id)).where(and_(
                RendezVous.clinic_id == clinic_id,
                RendezVous.date_heure_debut >= tomorrow_start,
                RendezVous.date_heure_debut <= tomorrow_end,
            ))
        )).scalar() or 0
        stock = (await session.execute(
            select(func.count(ProduitInjectable.id)).where(and_(
                ProduitInjectable.clinic_id == clinic_id,
                ProduitInjectable.stock_actuel <= ProduitInjectable.stock_alerte,
                ProduitInjectable.is_active == True,  # noqa
            ))
        )).scalar() or 0

        return {
            "date": today.isoformat(),
            "rdvs_today_count": len(rdvs),
            "rdvs_today_details": [
                {
                    "id": r.id, "heure": r.date_heure_debut.strftime("%H:%M"),
                    "patient": (
                        f"{getattr(r.patient, 'prenom', '')} "
                        f"{getattr(r.patient, 'nom', '')}"
                    ).strip(),
                    "acte": r.acte.nom if r.acte else "N/A",
                    "statut": r.statut,
                    "salle": r.salle or "N/A",
                } for r in rdvs
            ],
            "revenue_today": float(revenue_today),
            "unpaid_invoices": int(unpaid),
            "rdvs_tomorrow": int(rdv_tom),
            "stock_alerts": int(stock),
        }

    # ── API publique ─────────────────────────────────────────────

    @staticmethod
    async def get_daily_summary(
        session: AsyncSession, user_id: int, clinic_id: int = 1,
        settings: Any = None, llm: LLMClient = None,
    ) -> Dict[str, Any]:
        today = date.today()
        metrics = await DashboardIAService._raw_daily_metrics(session, clinic_id, today)
        result: Dict[str, Any] = {**metrics, "narrative": None, "llm_status": "skipped"}

        if llm is None and settings is not None:
            llm = get_llm_client(settings)
        if llm is not None:
            try:
                # Pseudonymisation des détails de la journée (noms patients)
                metrics_safe = pseudonymize_pii(metrics)
                
                msgs = DASHBOARD_NARRATION.render(
                    date=today.isoformat(),
                    metrics_json=json.dumps(metrics_safe, ensure_ascii=False, default=str),
                )
                out = await llm.chat(
                    msgs,
                    max_tokens=500,
                    response_format_json=True,
                    budget_subject=f"clinic:{clinic_id}:dashboard_narration",
                    budget_clinic_id=clinic_id,
                )
                if isinstance(out, LLMUnavailable):
                    result["llm_status"] = _status_marker(out)
                else:
                    try:
                        parsed = json.loads(out.text)
                        if isinstance(parsed.get("narrative"), str):
                            result["narrative"] = parsed["narrative"]
                        if isinstance(parsed.get("highlights"), list):
                            result["highlights"] = parsed["highlights"][:8]
                        if isinstance(parsed.get("actions"), list):
                            result["actions"] = parsed["actions"][:5]
                    except json.JSONDecodeError:
                        result["narrative"] = out.text
                    result["llm_status"] = "ok"
                    result["llm_provider"] = out.provider
            except Exception as exc:
                logger.exception("dashboard_daily_llm_error")
                result["llm_status"] = f"exception:{exc!r}"
        return result

    @staticmethod
    async def get_absent_patients(
        session: AsyncSession, clinic_id: int = 1, days: int = 30,
    ) -> Dict[str, Any]:
        cutoff = datetime.utcnow() - timedelta(days=days)
        stmt = select(Patient).where(
            and_(Patient.clinic_id == clinic_id,
                 or_(Patient.derniere_visite == None,  # noqa
                     Patient.derniere_visite < cutoff))
        ).limit(100)
        rows = (await session.execute(stmt)).scalars().all()
        return {
            "clinic_id": clinic_id,
            "days_window": days,
            "total_absent_patients": len(rows),
            "patients": [{
                "id": r.id,
                "nom": f"{getattr(r, 'prenom', '')} {getattr(r, 'nom', '')}".strip(),
                "last_visit": getattr(r, "derniere_visite", None),
                "telephone": getattr(r, "telephone", None),
                "absences": 1,  # Simplification pour le dashboard
                "loyalty": getattr(getattr(r, "niveau_fidelite", None), "value", None),
            } for r in rows],
        }

    @staticmethod
    async def get_vip_patients(
        session: AsyncSession, clinic_id: int = 1,
    ) -> Dict[str, Any]:
        stmt = select(Patient).where(and_(
            Patient.clinic_id == clinic_id,
            Patient.niveau_fidelite == NiveauFidelite.VIP.value,
        )).limit(50)
        rows = (await session.execute(stmt)).scalars().all()
        return {
            "clinic_id": clinic_id,
            "total_vip": len(rows),
            "patients": [{
                "id": r.id,
                "nom": f"{getattr(r, 'prenom', '')} {getattr(r, 'nom', '')}".strip(),
                "telephone": getattr(r, "telephone", None),
            } for r in rows],
        }

    @staticmethod
    async def get_ai_recommendations(
        session: AsyncSession, clinic_id: int = 1,
        settings: Any = None, llm: LLMClient = None,
    ) -> Dict[str, Any]:
        absent_data = await DashboardIAService.get_absent_patients(session, clinic_id=clinic_id, days=60)
        patients = absent_data.get("patients", [])
        result: Dict[str, Any] = {
            "clinic_id": clinic_id,
            "recommendations": [],
            "llm_status": "skipped",
        }
        
        if llm is None and settings is not None:
            llm = get_llm_client(settings)
            
        if llm is not None and patients:
            try:
                # Pseudonymisation de la liste des patients absents
                patients_safe = pseudonymize_pii(patients[:10])

                msgs = [
                    {"role": "system", "content": (
                        "Tu es directeur de clinique. Donne des recommandations au format JSON : "
                        "[{\"message\": \"...\", \"priority\": \"high|medium|low\", \"products\": [\"...\"]}]"
                    )},
                    {"role": "user", "content": (
                        "Patients absents :\n" +
                        json.dumps(patients_safe, ensure_ascii=False, default=str)
                    )},
                ]
                out = await llm.chat(
                    msgs,
                    max_tokens=800,
                    response_format_json=True,
                    budget_subject=f"clinic:{clinic_id}:dashboard_recommendations",
                    budget_clinic_id=clinic_id,
                )
                if isinstance(out, LLMUnavailable):
                    result["llm_status"] = _status_marker(out)
                else:
                    try:
                        result["recommendations"] = json.loads(out.text)
                    except (TypeError, json.JSONDecodeError):
                        result["recommendations"] = [{"message": out.text, "priority": "medium"}]
                    result["llm_status"] = "ok"
            except Exception as exc:
                logger.exception("dashboard_reco_llm_error")
                result["llm_status"] = f"exception:{exc!r}"
        
        # Fallback si vide
        if not result["recommendations"]:
            result["recommendations"] = [
                {"message": "Relancer les patients absents depuis 30 jours", "priority": "high", "products": ["Botox"]},
                {"message": "Offre spéciale VIP pour le mois prochain", "priority": "medium", "products": ["Peeling"]}
            ]
        return result

    @staticmethod
    async def get_revenue_forecast(
        session: AsyncSession, clinic_id: int = 1, days: int = 7,
        settings: Any = None, llm: LLMClient = None,
    ) -> Dict[str, Any]:
        # SQL forecast trivial (rolling average)
        horizon_start = datetime.utcnow() - timedelta(days=30)
        historic_revenue = (await session.execute(
            select(func.date(Facture.date_emission).label("d"),
                   func.sum(Facture.total_ttc).label("s"))
            .where(and_(
                Facture.clinic_id == clinic_id,
                Facture.date_emission >= horizon_start,
            ))
            .group_by(func.date(Facture.date_emission))
        )).all()
        days_with_data = len(historic_revenue) or 1
        avg_per_day = (
            sum(float(s or 0) for _, s in historic_revenue) / days_with_data
        )
        forecast_horizon = [date.today() + timedelta(days=i + 1) for i in range(days)]
        forecast = [
            {"date": d.isoformat(), "estimated_revenue": round(avg_per_day, 2)}
            for d in forecast_horizon
        ]
        result: Dict[str, Any] = {
            "clinic_id": clinic_id,
            "horizon_days": days,
            "average_daily_revenue": round(avg_per_day, 2),
            "forecast": forecast,
            "commentary": None,
            "llm_status": "skipped",
        }
        if llm is None and settings is not None:
            llm = get_llm_client(settings)
        if llm is not None:
            try:
                msgs = [
                    {"role": "system", "content": (
                        "Tu es analyste financier d'une clinique esthétique. "
                        "Commente en 2-3 phrases une prévision de CA basée sur "
                        "une moyenne quotidienne historique."
                    )},
                    {"role": "user", "content": (
                        f"Moyenne quotidienne : {avg_per_day:.2f} €. "
                        f"Horizon : {days} jours. "
                        f"Prévision totale : {round(avg_per_day * days, 2)} €.\n"
                        "Donne ton commentaire."
                    )},
                ]
                out = await llm.chat(
                    msgs,
                    max_tokens=250,
                    budget_subject=f"clinic:{clinic_id}:dashboard_forecast",
                    budget_clinic_id=clinic_id,
                )
                if isinstance(out, LLMUnavailable):
                    result["llm_status"] = _status_marker(out)
                else:
                    result["commentary"] = out.text
                    result["llm_status"] = "ok"
                    result["llm_provider"] = out.provider
            except Exception as exc:
                logger.exception("dashboard_forecast_llm_error")
                result["llm_status"] = f"exception:{exc!r}"
        return result

    @staticmethod
    async def get_cancellation_risk(
        session: AsyncSession, clinic_id: int = 1, horizon_days: int = 30,
    ) -> Dict[str, Any]:
        """Calcule le risque d'annulation/no-show à partir de l'historique réel.

        Le score est une fréquence empirique lissée : (événements défavorables + 1)
        / (rendez-vous historiques + 2). Il n'utilise ni valeur fictive ni LLM et
        retourne explicitement la taille de l'historique servant au calcul.
        """
        now = datetime.utcnow()
        history = (await session.execute(
            select(RendezVous).where(and_(
                RendezVous.clinic_id == clinic_id,
                RendezVous.date_heure_debut < now,
            ))
        )).scalars().all()
        upcoming = (await session.execute(
            select(RendezVous).where(and_(
                RendezVous.clinic_id == clinic_id,
                RendezVous.date_heure_debut >= now,
                RendezVous.date_heure_debut < now + timedelta(days=horizon_days),
                RendezVous.statut.notin_([StatutRDV.ANNULE.value, StatutRDV.NO_SHOW.value]),
            )).options(selectinload(RendezVous.patient), selectinload(RendezVous.praticien))
        )).scalars().all()

        by_patient: Dict[int, Dict[str, int]] = {}
        for rdv in history:
            stats = by_patient.setdefault(rdv.patient_id, {"total": 0, "bad": 0})
            stats["total"] += 1
            if rdv.statut in (StatutRDV.ANNULE.value, StatutRDV.NO_SHOW.value):
                stats["bad"] += 1

        clinic_total = len(history)
        clinic_bad = sum(1 for r in history if r.statut in (StatutRDV.ANNULE.value, StatutRDV.NO_SHOW.value))
        clinic_rate = (clinic_bad + 1) / (clinic_total + 2)
        risks = []
        for rdv in upcoming:
            stats = by_patient.get(rdv.patient_id, {"total": 0, "bad": 0})
            score = (stats["bad"] + 1) / (stats["total"] + 2) if stats["total"] else clinic_rate
            risks.append({
                "rdv_id": rdv.id,
                "patient_id": rdv.patient_id,
                "patient": f"{getattr(rdv.patient, 'prenom', '')} {getattr(rdv.patient, 'nom', '')}".strip(),
                "praticien_id": rdv.praticien_id,
                "praticien": f"{getattr(rdv.praticien, 'prenom', '')} {getattr(rdv.praticien, 'nom', '')}".strip(),
                "date_heure": rdv.date_heure_debut.isoformat(),
                "risk_score": round(score, 4),
                "historical_appointments": stats["total"],
                "historical_cancellations_or_no_shows": stats["bad"],
                "risk_level": "high" if score >= 0.50 else "medium" if score >= 0.25 else "low",
            })
        risks.sort(key=lambda item: (-item["risk_score"], item["date_heure"]))
        return {
            "clinic_id": clinic_id,
            "horizon_days": horizon_days,
            "historical_appointments": clinic_total,
            "historical_cancellations_or_no_shows": clinic_bad,
            "clinic_baseline_risk": round(clinic_rate, 4),
            "appointments": risks,
            "data_source": "rendez_vous.statut/date_heure_debut",
        }

    @staticmethod
    async def get_practitioner_performance(
        session: AsyncSession, clinic_id: int = 1,
    ) -> Dict[str, Any]:
        rows = (await session.execute(
            select(
                Utilisateur.id, Utilisateur.prenom, Utilisateur.nom, Utilisateur.specialite,
                RendezVous.id, RendezVous.statut, Facture.total_ttc, DossierMedical.satisfaction_patient,
            )
            .outerjoin(RendezVous, and_(RendezVous.praticien_id == Utilisateur.id, RendezVous.clinic_id == clinic_id))
            .outerjoin(Facture, and_(Facture.rdv_id == RendezVous.id, Facture.clinic_id == clinic_id))
            .outerjoin(DossierMedical, DossierMedical.rdv_id == RendezVous.id)
            .where(Utilisateur.clinic_id == clinic_id)
        )).all()
        grouped: Dict[int, Dict[str, Any]] = {}
        for row in rows:
            pid, prenom, nom, specialite, rdv_id, statut, total_ttc, satisfaction = row
            item = grouped.setdefault(pid, {"id": pid, "nom": f"{prenom or ''} {nom or ''}".strip(), "specialite": specialite or "Général", "rdvs_total": 0, "rdvs_completed": 0, "revenue": 0.0, "satisfactions": []})
            if rdv_id is not None:
                item["rdvs_total"] += 1
                if statut == StatutRDV.TERMINE.value:
                    item["rdvs_completed"] += 1
            if total_ttc is not None and statut == StatutRDV.TERMINE.value:
                item["revenue"] += float(total_ttc)
            if satisfaction is not None:
                item["satisfactions"].append(int(satisfaction))
        practitioners = []
        for item in grouped.values():
            values = item.pop("satisfactions")
            item["revenue"] = round(item["revenue"], 3)
            item["avg_satisfaction"] = round(sum(values) / len(values), 2) if values else None
            practitioners.append(item)
        practitioners.sort(key=lambda item: (-item["rdvs_total"], item["nom"]))
        return {"clinic_id": clinic_id, "practitioners": practitioners[:20], "data_source": "rendez_vous/factures/dossiers_medicaux"}

    @staticmethod
    async def get_dashboard_widgets_config(
        session: AsyncSession, user_id: int, clinic_id: int = 1,
    ) -> Dict[str, Any]:
        return {
            "clinic_id": clinic_id,
            "user_id": user_id,
            "widgets": [
                {"key": "daily_summary", "title": "Résumé du jour", "type": "narration"},
                {"key": "rdv_today", "title": "RDV d'aujourd'hui", "type": "list"},
                {"key": "revenue_today", "title": "Recettes du jour", "type": "kpi"},
                {"key": "stock_alerts", "title": "Alertes stock", "type": "alerts"},
                {"key": "vip_patients", "title": "Patients VIP", "type": "list"},
                {"key": "revenue_forecast", "title": "Prévision 7 jours", "type": "chart+commentary"},
                {"key": "ai_recommendations", "title": "Recommandations IA", "type": "list"},
                {"key": "cancellation_risk", "title": "Risque d'annulation", "type": "risk-list"},
            ],
        }

    @staticmethod
    async def get_full_dashboard(
        session: AsyncSession, user_id: int, clinic_id: int = 1,
        settings: Any = None, llm: LLMClient = None,
    ) -> Dict[str, Any]:
        try:
            daily = await DashboardIAService.get_daily_summary(session, user_id, clinic_id, settings, llm)
            forecast = await DashboardIAService.get_revenue_forecast(session, clinic_id, 7, settings, llm)
            absent = await DashboardIAService.get_absent_patients(session, clinic_id, 30)
            vip = await DashboardIAService.get_vip_patients(session, clinic_id)
            recos = await DashboardIAService.get_ai_recommendations(session, clinic_id, settings, llm)
            perf = await DashboardIAService.get_practitioner_performance(session, clinic_id)
            cancellation_risk = await DashboardIAService.get_cancellation_risk(session, clinic_id)
            config = await DashboardIAService.get_dashboard_widgets_config(session, user_id, clinic_id)
            
            return {
                "clinic_id": clinic_id,
                "timestamp": datetime.utcnow().isoformat(),
                "daily_summary": daily,
                "revenue_forecast": forecast,
                "absent_patients": absent,
                "vip_patients": vip,
                "ai_recommendations": recos,
                "practitioner_performance": perf,
                "cancellation_risk": cancellation_risk,
                "widgets_config": config
            }
        except Exception as exc:
            logger.exception("dashboard_full_error")
            return {"error": str(exc), "clinic_id": clinic_id}
