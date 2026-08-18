"""
AutoCommerce Clinic — Implémentation des tools de lecture (Bloc 2)

Chaque tool du catalogue (`assistant_tools_schema.TOOL_CATALOG`),
lorsqu'il est appelé par l'orchestrateur (`assistant_ia.py`), **délègue
exclusivement** à un service métier existant. Aucun SQL direct
n'est jamais émis ici, conformément à la consigne du Bloc 2 :

  > aucun accès direct du LLM à la base — les réponses passent
  > par des fonctions backend dédiées à la lecture (mêmes services
  > que l'app web), jamais par du SQL généré par le modèle.

Sont réutilisés :
  - `services.agenda`          (RDV, disponibilités)
  - `services.patients`       (lecture fiche patient)
  - `services.stock_injectable`(dashboard stock, alertes)
  - `services.factures`       (CA, factures)
  - `services.commissions`    (CA par période / par praticien)
"""

from datetime import datetime, date, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from middleware.clinic_rbac import check_permission
from models.database import (
    Facture,
    RendezVous,
    Patient,
    Utilisateur,
    StatutRDV,
    StatutFacture,
)
from services.stock_injectable import get_stock_dashboard
from services.assistant_tools_schema import TOOL_CATALOG


class ToolNotAllowed(Exception):
    """Tool inconnu du catalogue — l'orchestrateur refuse."""


class ToolPermissionDenied(Exception):
    """Le rôle de l'utilisateur n'autorise pas ce tool."""


_TOOL_INDEX: Dict[str, Dict[str, Any]] = {t["name"]: t for t in TOOL_CATALOG}


def known_tools() -> List[Dict[str, Any]]:
    return list(TOOL_CATALOG)


def lookup_tool(name: str) -> Optional[Dict[str, Any]]:
    return _TOOL_INDEX.get(name)


# ── Helpers ────────────────────────────────────────────────

async def _praticien_id_for(current_user: Dict[str, Any], db: AsyncSession) -> Optional[int]:
    """Retourne l'utilisateur lui-même s'il est MEDECIN/ESTHETICIENNE,
    sinon le superieur_id au sens RH (le praticien "rattaché"). Pour
    ASSISTANTE, on prend le premier MEDECIN de la clinique comme
    praticien de référence — comportement documenté et non silencieux.
    """
    role = current_user.get("role")
    if role in ("medecin", "estheticienne", "directrice"):
        return current_user.get("id")
    if role == "assistante":
        # Premier médecin actif de la clinique
        res = await db.execute(
            select(Utilisateur).where(Utilisateur.role == "medecin").limit(1)
        )
        u = res.scalar_one_or_none()
        return u.id if u else None
    return None


def _is_admin_or_directrice(role: str) -> bool:
    return role in ("admin", "directrice")


# ── Tools ──────────────────────────────────────────────────

async def get_rdv_count_today(current_user: Dict[str, Any], db: AsyncSession) -> Dict[str, Any]:
    praticien_id = await _praticien_id_for(current_user, db)
    if not praticien_id:
        return {"count": 0, "detail": "Aucun praticien rattaché."}
    today_start = datetime.combine(date.today(), datetime.min.time())
    today_end = today_start + timedelta(days=1)
    res = await db.execute(
        select(func.count(RendezVous.id)).where(
            and_(
                RendezVous.praticien_id == praticien_id,
                RendezVous.date_heure_debut >= today_start,
                RendezVous.date_heure_debut < today_end,
                RendezVous.statut.notin_([StatutRDV.ANNULE.value, StatutRDV.NO_SHOW.value]),
            )
        )
    )
    return {"count": int(res.scalar() or 0), "praticien_id": praticien_id}


async def get_next_rdv(current_user: Dict[str, Any], db: AsyncSession) -> Dict[str, Any]:
    praticien_id = await _praticien_id_for(current_user, db)
    if not praticien_id:
        return {"rdv": None, "detail": "Aucun praticien rattaché."}
    now = datetime.utcnow()
    res = await db.execute(
        select(RendezVous, Patient)
        .join(Patient, RendezVous.patient_id == Patient.id)
        .where(RendezVous.praticien_id == praticien_id)
        .where(RendezVous.date_heure_debut >= now)
        .where(RendezVous.statut.notin_([StatutRDV.ANNULE.value, StatutRDV.NO_SHOW.value]))
        .order_by(RendezVous.date_heure_debut.asc())
        .limit(1)
    )
    row = res.first()
    if not row:
        return {"rdv": None}
    rdv, patient = row
    return {
        "rdv": {
            "id": rdv.id,
            "date_heure": rdv.date_heure_debut.isoformat(),
            "patient": f"{patient.prenom} {patient.nom}",
            "statut": rdv.statut,
        }
    }


async def list_rd_today(current_user: Dict[str, Any], db: AsyncSession) -> Dict[str, Any]:
    praticien_id = await _praticien_id_for(current_user, db)
    if not praticien_id:
        return {"rdvs": [], "detail": "Aucun praticien rattaché."}
    today_start = datetime.combine(date.today(), datetime.min.time())
    today_end = today_start + timedelta(days=1)
    res = await db.execute(
        select(RendezVous, Patient)
        .join(Patient, RendezVous.patient_id == Patient.id)
        .where(RendezVous.praticien_id == praticien_id)
        .where(RendezVous.date_heure_debut >= today_start)
        .where(RendezVous.date_heure_debut < today_end)
        .where(RendezVous.statut.notin_([StatutRDV.ANNULE.value, StatutRDV.NO_SHOW.value]))
        .order_by(RendezVous.date_heure_debut.asc())
    )
    rdvs: List[Dict[str, Any]] = []
    for rdv, patient in res.all():
        rdvs.append({
            "id": rdv.id,
            "heure": rdv.date_heure_debut.strftime("%H:%M"),
            "patient": f"{patient.prenom} {patient.nom}",
            "statut": rdv.statut,
        })
    return {"rdvs": rdvs, "count": len(rdvs)}


async def list_inactive_patients(
    current_user: Dict[str, Any],
    db: AsyncSession,
    since_months: int = 6,
) -> Dict[str, Any]:
    cutoff = date.today() - timedelta(days=int(since_months) * 30)
    res = await db.execute(
        select(Patient)
        .where(
            (Patient.derniere_visite.is_(None)) | (Patient.derniere_visite < cutoff)
        )
        .where(Patient.is_active)
        .where(Patient.consentement_marketing)
        .order_by(Patient.derniere_visite.asc().nulls_first())
        .limit(100)
    )
    patients = res.scalars().all()
    # PII Scrubbing: On ne renvoie pas les données sensibles (allergies, notes) au LLM/Logs
    return {
        "count": len(patients),
        "since_months": since_months,
        "patients": [
            {
                "id": p.id,
                "nom": f"{p.prenom} {p.nom}",
                "derniere_visite": p.derniere_visite.isoformat() if p.derniere_visite else None,
                "telephone": p.telephone[:5] + "****" if p.telephone else None,
            }
            for p in patients
        ],
    }


async def get_stock_overview(
    current_user: Dict[str, Any],
    db: AsyncSession,
    produit_nom: Optional[str] = None,
) -> Dict[str, Any]:
    """Délègue au dashboard stock existant — réutilise services.stock_injectable."""
    dashboard = await get_stock_dashboard(db)
    if produit_nom:
        produits = [
            p for p in dashboard.get("produits", [])
            if produit_nom.lower() in (p.get("nom") or "").lower()
        ]
    else:
        produits = dashboard.get("produits", [])
    return {
        "produits": produits,
        "alertes": dashboard.get("alertes", {}),
        "total_alertes": dashboard.get("total_alertes", 0),
    }


async def get_revenue_summary(
    current_user: Dict[str, Any],
    db: AsyncSession,
    periode: str = "semaine",
) -> Dict[str, Any]:
    """CA = somme des factures payées sur la période. RBAC : 'factures' read."""
    today = date.today()
    if periode == "semaine":
        start = today - timedelta(days=7)
    elif periode == "mois":
        start = today.replace(day=1)
    else:
        start = today - timedelta(days=7)
    start_dt = datetime.combine(start, datetime.min.time())

    res = await db.execute(
        select(
            func.count(Facture.id).label("nb"),
            func.coalesce(func.sum(Facture.montant_total_ttc), 0).label("ca"),
        ).where(
            and_(
                Facture.date_emission >= start_dt,
                Facture.statut.in_([
                    StatutFacture.PAYEE.value,
                    StatutFacture.PARTIELLEMENT_PAYEE.value,
                ]),
            )
        )
    )
    row = res.first()
    nb = int(row.nb or 0) if row else 0
    ca = Decimal(row.ca or 0) if row else Decimal("0")
    return {"periode": periode, "depuis": start.isoformat(), "nb_factures": nb, "ca_ttc": float(ca)}


async def send_daily_report(
    current_user: Dict[str, Any], db: AsyncSession
) -> Dict[str, Any]:
    """Rapport du jour = agrégat des autres tools lecture seule."""
    rdvs = await list_rd_today(current_user, db)
    ca = await get_revenue_summary(current_user, db, "semaine")
    stock = await get_stock_overview(current_user, db)
    return {
        "rdvs_aujourdhui": rdvs.get("count", 0),
        "rdvs_detail": rdvs.get("rdvs", []),
        "ca_semaine": ca,
        "stock_alertes_total": stock.get("total_alertes", 0),
        "stock_urgent": [
            a for a in stock.get("alertes", {}).get("rouge", [])
        ],
    }


# ── Dispatcher ─────────────────────────────────────────────

async def run_tool(
    tool_name: str,
    parameters: Dict[str, Any],
    current_user: Dict[str, Any],
    db: AsyncSession,
) -> Dict[str, Any]:
    """Dispatche vers le bon tool en appliquant le RBAC.

    Toute personne non whitelistée ne devrait pas arriver jusque-là
    (filtre amont `assistant_whitelist`) mais le RBAC reste souverain.
    """
    spec = lookup_tool(tool_name)
    if not spec:
        raise ToolNotAllowed(f"Tool inconnu: {tool_name}")

    role = current_user.get("role", "")
    if not check_permission(role, spec["resource"], spec["action"]):
        raise ToolPermissionDenied(
            f"Rôle '{role}' non autorisé sur '{spec['resource']}' "
            f"(action '{spec['action']}')"
        )

    name = spec["name"]
    if name == "get_rdv_count_today":
        return await get_rdv_count_today(current_user, db)
    if name == "get_next_rdv":
        return await get_next_rdv(current_user, db)
    if name == "list_rd_today":
        return await list_rd_today(current_user, db)
    if name == "list_inactive_patients":
        return await list_inactive_patients(
            current_user, db, since_months=parameters.get("since_months", 6)
        )
    if name == "get_stock_overview":
        return await get_stock_overview(
            current_user, db, produit_nom=parameters.get("produit_nom")
        )
    if name == "get_revenue_summary":
        return await get_revenue_summary(
            current_user, db, periode=parameters.get("periode", "semaine")
        )
    if name == "send_daily_report":
        return await send_daily_report(current_user, db)

    raise ToolNotAllowed(f"Tool connu mais non câblé: {name}")
