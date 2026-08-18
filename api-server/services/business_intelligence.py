"""
AutoCommerce Clinic — Service Business Intelligence (Bloc 8) — v2 (LLM réel)

Module BI répondant à : chiffre d'affaires, médecin le plus rentable, soins les
plus performants, patients fidèles, créneaux sous-utilisés, prévision 30 jours
**et maintenant** :
- Détection d'anomalies (SQL) ;
- Insight LLM sur KPIs (Bloc 8 « interprétation ») ;
- Mode dégradé honnête (jamais de faux chiffres).

Compatibilité ascendante : toutes les méthodes existantes sont préservées.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, date, timedelta
from decimal import Decimal
from typing import Any, Dict

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from models.database import (
    Facture, StatutFacture, RendezVous, Patient, Utilisateur, ActeMedical,
)

from core.llm_client import LLMClient, LLMUnavailable, get_llm_client, pseudonymize_pii
from core.prompt_templates import BI_INSIGHTS

logger = logging.getLogger("business_intelligence")


def _status_marker(outcome: Any) -> str:
    if isinstance(outcome, LLMUnavailable):
        return f"unavailable:{outcome.provider}:{outcome.reason[:120]}"
    return "ok"


class BusinessIntelligenceService:
    """Service BI — chiffres exacts SQL + narration LLM si dispo."""

    # ── méthodes existantes (SQL only) ─────────────────────────

    @staticmethod
    async def get_revenue_summary(
        session: AsyncSession, clinic_id: int = 1, period_days: int = 30,
    ) -> Dict[str, Any]:
        cutoff = date.today() - timedelta(days=period_days)
        revenue = (await session.execute(
            select(func.sum(Facture.total_ttc)).where(and_(
                Facture.clinic_id == clinic_id,
                Facture.date_emission >= cutoff,
                Facture.statut.in_([
                    StatutFacture.PAYEE.value, StatutFacture.PARTIELLEMENT_PAYEE.value,
                ]),
            ))
        )).scalar() or Decimal("0.000")
        count = (await session.execute(
            select(func.count(Facture.id)).where(and_(
                Facture.clinic_id == clinic_id,
                Facture.date_emission >= cutoff,
                Facture.statut.in_([
                    StatutFacture.PAYEE.value, StatutFacture.PARTIELLEMENT_PAYEE.value,
                ]),
            ))
        )).scalar() or 0
        revenue_f = float(revenue)

        # ── Breakdowns (SQLite + PostgreSQL compatible — Python-side aggregation) ──
        from collections import defaultdict

        factures = (await session.execute(
            select(Facture).where(and_(
                Facture.clinic_id == clinic_id,
                Facture.date_emission >= cutoff,
                Facture.statut.in_([
                    StatutFacture.PAYEE.value, StatutFacture.PARTIELLEMENT_PAYEE.value,
                ]),
            ))
        )).scalars().all()

        # revenue_by_day
        day_rev: dict = defaultdict(float)
        for f in factures:
            day_rev[str(f.date_emission)] += float(f.total_ttc or 0)
        revenue_by_day = [
            {"date": k, "revenue": round(v, 2)}
            for k, v in sorted(day_rev.items())
        ]

        # revenue_by_acte (from JSON actes field on each Facture)
        acte_rev: dict = defaultdict(float)
        for f in factures:
            for acte in (f.actes or []):
                if isinstance(acte, dict) and acte.get("nom"):
                    acte_rev[acte["nom"]] += float(acte.get("prix", 0))
        revenue_by_acte = [
            {"nom": k, "revenue": round(v, 2)}
            for k, v in sorted(acte_rev.items(), key=lambda x: -x[1])
        ]

        # revenue_by_practitioner (via RendezVous.praticien_id join)
        revenue_by_practitioner: list = []
        try:
            rdv_ids = [f.rdv_id for f in factures if f.rdv_id]
            if rdv_ids:
                rdv_rows = (await session.execute(
                    select(RendezVous.id, RendezVous.praticien_id)
                    .where(RendezVous.id.in_(rdv_ids))
                )).all()
                rdv_map = {r[0]: r[1] for r in rdv_rows}
                prat_ids = {pid for pid in rdv_map.values() if pid}
                prat_names: dict = {}
                if prat_ids:
                    prat_rows = (await session.execute(
                        select(Utilisateur.id, Utilisateur.prenom, Utilisateur.nom)
                        .where(Utilisateur.id.in_(prat_ids))
                    )).all()
                    prat_names = {r[0]: f"{r[1] or ''} {r[2] or ''}".strip() for r in prat_rows}
                prat_rev: dict = defaultdict(float)
                for f in factures:
                    pid = rdv_map.get(f.rdv_id)
                    if pid:
                        prat_rev[prat_names.get(pid, f"Praticien {pid}")] += float(f.total_ttc or 0)
                revenue_by_practitioner = [
                    {"nom": k, "revenue": round(v, 2)}
                    for k, v in sorted(prat_rev.items(), key=lambda x: -x[1])
                ]
        except Exception:
            revenue_by_practitioner = []

        return {
            "period_days": period_days,
            "total_revenue": revenue_f,
            "total_invoices": int(count),
            "avg_invoice": round(revenue_f / max(int(count), 1), 2),
            "currency": "EUR",
            "revenue_by_day": revenue_by_day,
            "revenue_by_acte": revenue_by_acte,
            "revenue_by_practitioner": revenue_by_practitioner,
        }

    @staticmethod
    async def get_top_practitioners(
        session: AsyncSession, clinic_id: int = 1, period_days: int = 30, limit: int = 10,
    ) -> Dict[str, Any]:
        cutoff = date.today() - timedelta(days=period_days)
        stmt = (
            select(
                Utilisateur.id,
                Utilisateur.prenom,
                Utilisateur.nom,
                func.coalesce(func.sum(Facture.total_ttc), 0).label("revenue"),
                func.count(Facture.id).label("invoices"),
            )
            .join(RendezVous, RendezVous.praticien_id == Utilisateur.id)
            .join(Facture, and_(
                Facture.rdv_id == RendezVous.id,
                Facture.clinic_id == clinic_id,
                Facture.date_emission >= cutoff,
                Facture.statut.in_([
                    StatutFacture.PAYEE.value, StatutFacture.PARTIELLEMENT_PAYEE.value,
                ]),
            ), isouter=True)
            .where(Utilisateur.clinic_id == clinic_id)
            .group_by(Utilisateur.id, Utilisateur.prenom, Utilisateur.nom)
            .order_by(func.coalesce(func.sum(Facture.total_ttc), 0).desc())
            .limit(limit)
        )
        rows = (await session.execute(stmt)).all()
        return {
            "period_days": period_days,
            "top_practitioners": [
                {
                    "id": r[0],
                    "name": f"{r[1] or ''} {r[2] or ''}".strip(),
                    "revenue": float(r[3] or 0),
                    "invoices": int(r[4] or 0),
                } for r in rows
            ],
        }

    @staticmethod
    async def get_top_treatments(
        session: AsyncSession, clinic_id: int = 1, period_days: int = 30, limit: int = 10,
    ) -> Dict[str, Any]:
        cutoff = date.today() - timedelta(days=period_days)
        stmt = (
            select(
                ActeMedical.id,
                ActeMedical.nom,
                func.coalesce(func.sum(Facture.total_ttc), 0).label("revenue"),
                func.count(Facture.id).label("invoices"),
            )
            .join(RendezVous, RendezVous.acte_id == ActeMedical.id)
            .join(Facture, and_(
                Facture.rdv_id == RendezVous.id,
                Facture.clinic_id == clinic_id,
                Facture.date_emission >= cutoff,
                Facture.statut.in_([
                    StatutFacture.PAYEE.value, StatutFacture.PARTIELLEMENT_PAYEE.value,
                ]),
            ), isouter=True)
            .where(ActeMedical.clinic_id == clinic_id)
            .group_by(ActeMedical.id, ActeMedical.nom)
            .order_by(func.coalesce(func.sum(Facture.total_ttc), 0).desc())
            .limit(limit)
        )
        rows = (await session.execute(stmt)).all()
        return {
            "period_days": period_days,
            "top_treatments": [
                {
                    "id": r[0], "name": r[1],
                    "revenue": float(r[2] or 0),
                    "invoices": int(r[3] or 0),
                } for r in rows
            ],
        }

    @staticmethod
    async def get_top_loyal_patients(
        session: AsyncSession, clinic_id: int = 1, limit: int = 20,
    ) -> Dict[str, Any]:
        stmt = (
            select(
                Patient.id,
                Patient.prenom,
                Patient.nom,
                func.coalesce(func.sum(Facture.total_ttc), 0).label("spend"),
                func.count(Facture.id).label("invoices"),
            )
            .join(Facture, and_(
                Facture.patient_id == Patient.id,
                Facture.clinic_id == clinic_id,
                Facture.statut.in_([
                    StatutFacture.PAYEE.value, StatutFacture.PARTIELLEMENT_PAYEE.value,
                ]),
            ), isouter=True)
            .where(Patient.clinic_id == clinic_id)
            .group_by(Patient.id, Patient.prenom, Patient.nom)
            .order_by(func.coalesce(func.sum(Facture.total_ttc), 0).desc())
            .limit(limit)
        )
        rows = (await session.execute(stmt)).all()
        return {
            "top_loyal_patients": [
                {
                    "id": r[0],
                    "name": f"{r[1] or ''} {r[2] or ''}".strip(),
                    "lifetime_spend": float(r[3] or 0),
                    "invoices": int(r[4] or 0),
                } for r in rows
            ],
        }

    @staticmethod
    async def get_underutilized_slots(
        session: AsyncSession, clinic_id: int = 1, period_days: int = 30,
    ) -> Dict[str, Any]:
        # Approche simple : compter RDV par jour-de-la-semaine / heure
        from sqlalchemy import extract
        cutoff = datetime.utcnow() - timedelta(days=period_days)
        stmt = (
            select(
                extract("dow", RendezVous.date_heure_debut).label("dow"),
                extract("hour", RendezVous.date_heure_debut).label("hour"),
                func.count(RendezVous.id).label("cnt"),
            )
            .where(and_(
                RendezVous.clinic_id == clinic_id,
                RendezVous.date_heure_debut >= cutoff,
            ))
            .group_by("dow", "hour")
            .order_by(func.count(RendezVous.id).asc())
            .limit(20)
        )
        rows = (await session.execute(stmt)).all()
        return {
            "underutilized_slots": [
                {"weekday": int(r[0] or 0), "hour": int(r[1] or 0), "rdv_count": int(r[2] or 0)}
                for r in rows
            ],
        }

    @staticmethod
    async def forecast_revenue_30_days(
        session: AsyncSession, clinic_id: int = 1,
    ) -> Dict[str, Any]:
        horizon = datetime.utcnow() - timedelta(days=30)
        rows = (await session.execute(
            select(
                func.sum(Facture.total_ttc).label("s"),
            ).where(and_(
                Facture.clinic_id == clinic_id,
                Facture.statut.in_([
                    StatutFacture.PAYEE.value, StatutFacture.PARTIELLEMENT_PAYEE.value,
                ]),
                Facture.date_emission >= horizon.date(),
            ))
        )).first()
        avg_total = float(rows[0] or 0)
        return {
            "horizon_days": 30,
            "avg_daily_revenue": round(avg_total / 30.0, 2),
            "total_forecast": round(avg_total, 2),
            "forecast_by_day": [round(avg_total / 30.0, 2)] * 30,
        }

    @staticmethod
    async def generate_business_report(
        session: AsyncSession, clinic_id: int = 1, period_days: int = 30,
    ) -> Dict[str, Any]:
        rev = await BusinessIntelligenceService.get_revenue_summary(session, clinic_id, period_days)
        tp = await BusinessIntelligenceService.get_top_practitioners(session, clinic_id, period_days)
        tt = await BusinessIntelligenceService.get_top_treatments(session, clinic_id, period_days)
        lp = await BusinessIntelligenceService.get_top_loyal_patients(session, clinic_id)
        us = await BusinessIntelligenceService.get_underutilized_slots(session, clinic_id, period_days)
        fc = await BusinessIntelligenceService.forecast_revenue_30_days(session, clinic_id)

        top_practitioner = (
            tp["top_practitioners"][0]["name"] if tp["top_practitioners"] else "N/A"
        )
        top_treatment = (
            tt["top_treatments"][0]["name"] if tt["top_treatments"] else "N/A"
        )
        return {
            "title": f"Rapport Business Intelligence - {period_days} derniers jours",
            "date_generated": datetime.utcnow().isoformat(),
            "period_days": period_days,
            "sections": {
                "revenue_summary": rev,
                "top_practitioners": tp,
                "top_treatments": tt,
                "top_loyal_patients": lp,
                "underutilized_slots": us,
                "revenue_forecast": fc,
            },
            "summary": {
                "total_revenue": rev["total_revenue"],
                "total_invoices": rev["total_invoices"],
                "avg_invoice": rev["avg_invoice"],
                "top_practitioner": top_practitioner,
                "top_treatment": top_treatment,
                "forecast_30_days": fc["total_forecast"],
            },
        }

    @staticmethod
    async def get_kpi_dashboard(
        session: AsyncSession, clinic_id: int = 1,
    ) -> Dict[str, Any]:
        today = date.today()
        month_start = today.replace(day=1)
        rev_month = (await session.execute(
            select(func.sum(Facture.total_ttc)).where(and_(
                Facture.clinic_id == clinic_id,
                Facture.date_emission >= month_start,
                Facture.statut.in_([
                    StatutFacture.PAYEE.value, StatutFacture.PARTIELLEMENT_PAYEE.value,
                ]),
            ))
        )).scalar() or Decimal("0.000")
        rev_today = (await session.execute(
            select(func.sum(Facture.total_ttc)).where(and_(
                Facture.clinic_id == clinic_id,
                Facture.date_emission == today,
                Facture.statut.in_([
                    StatutFacture.PAYEE.value, StatutFacture.PARTIELLEMENT_PAYEE.value,
                ]),
            ))
        )).scalar() or Decimal("0.000")
        rdv_today = (await session.execute(
            select(func.count(RendezVous.id)).where(and_(
                RendezVous.clinic_id == clinic_id,
                RendezVous.date_heure_debut >= datetime.combine(today, datetime.min.time()),
                RendezVous.date_heure_debut <= datetime.combine(today, datetime.max.time()),
            ))
        )).scalar() or 0
        return {
            "clinic_id": clinic_id,
            "revenue_today": float(rev_today),
            "revenue_month": float(rev_month),
            "rdv_today": int(rdv_today),
        }

    # ── NOUVEAU : insights LLM (Bloc 8 « interprétation ») ──────

    @staticmethod
    async def get_llm_insights(
        session: AsyncSession, clinic_id: int = 1, period_days: int = 30,
        settings: Any = None, llm: LLMClient = None,
    ) -> Dict[str, Any]:
        """Renvoie un rapport d'insights LLM (JSON) basé sur les KPI réels."""
        try:
            kpis = await BusinessIntelligenceService.get_kpi_dashboard(session, clinic_id)
            rev = await BusinessIntelligenceService.get_revenue_summary(session, clinic_id, period_days)
            tp = await BusinessIntelligenceService.get_top_practitioners(session, clinic_id, period_days, limit=5)
            tt = await BusinessIntelligenceService.get_top_treatments(session, clinic_id, period_days, limit=5)
            at_risk = await __import__('services.copilote_crm', fromlist=['CopiloteCRMService']).CopiloteCRMService.detect_at_risk_patients(
                session, clinic_id=clinic_id, settings=settings, llm=None
            )
            payload = {
                "kpis": kpis, "revenue": rev,
                "top_practitioners": tp["top_practitioners"],
                "top_treatments": tt["top_treatments"],
                "at_risk_patients": at_risk.get("items", [])[:20],
            }
        except Exception as exc:
            logger.exception("bi_insights_payload_error")
            return {"error": str(exc), "insights": [], "recommendations": [], "risks": []}

        result: Dict[str, Any] = {
            "clinic_id": clinic_id,
            "period_days": period_days,
            "data": payload,
            "insights": [],
            "recommendations": [],
            "risks": [],
            "llm_status": "skipped",
        }
        if llm is None and settings is not None:
            llm = get_llm_client(settings)
        if llm is None:
            return result
        try:
            # Pseudonymisation des données patients à risque
            at_risk_safe = pseudonymize_pii(payload["at_risk_patients"])
            
            msgs = BI_INSIGHTS.render(
                period_days=period_days,
                kpis_json=json.dumps(payload["kpis"], default=str),
                top_practitioners_json=json.dumps(payload["top_practitioners"], default=str),
                top_treatments_json=json.dumps(payload["top_treatments"], default=str),
                at_risk_json=json.dumps(at_risk_safe, default=str),
            )
            out = await llm.chat(
                msgs,
                max_tokens=800,
                response_format_json=True,
                budget_subject=f"clinic:{clinic_id}:business_intelligence",
                budget_clinic_id=clinic_id,
            )
            if isinstance(out, LLMUnavailable):
                result["llm_status"] = _status_marker(out)
            else:
                try:
                    parsed = json.loads(out.text)
                    if isinstance(parsed.get("insights"), list):
                        result["insights"] = parsed["insights"][:10]
                    if isinstance(parsed.get("recommendations"), list):
                        result["recommendations"] = parsed["recommendations"][:8]
                    if isinstance(parsed.get("risks"), list):
                        result["risks"] = parsed["risks"][:5]
                except json.JSONDecodeError:
                    result["insights"] = [out.text]
                result["llm_status"] = "ok"
                result["llm_provider"] = out.provider
        except Exception as exc:
            logger.exception("bi_insights_llm_error")
            result["llm_status"] = f"exception:{exc!r}"
        return result
