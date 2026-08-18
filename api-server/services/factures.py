"""
AutoCommerce Clinic — Service Factures

Calcul des totaux (jamais de float pour les montants — Decimal
partout, cf. règle absolue du projet), numérotation séquentielle
par année, et déclenchement automatique de la commission commerciale
+ des points de fidélité au moment du paiement.
"""
from datetime import date
from decimal import Decimal
from typing import Optional

from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError

from models.database import Facture, Patient, StatutFacture
from config import get_settings
from services.commissions import create_commission
from services.fidelite import add_points

# 1 point de fidélité par tranche de 10 (unité monétaire) dépensée
POINTS_PAR_UNITE = Decimal("10")


async def _generate_numero_facture(db) -> str:
    annee = date.today().year
    result = await db.execute(
        select(func.count(Facture.id)).where(
            Facture.numero_facture.like(f"F-{annee}-%")
        )
    )
    count = result.scalar_one()
    return f"F-{annee}-{count + 1:04d}"


def _json_lines(lines: list[dict] | None) -> list[dict]:
    """Convertit les montants Decimal en valeurs JSON sérialisables."""
    return [
        {
            **line,
            "prix": str(Decimal(str(line["prix"]))),
            "quantite": int(line.get("quantite", 1)),
        }
        for line in (lines or [])
    ]


def _compute_totals(actes: list[dict], produits: list[dict], remise_globale_pct: Decimal,
                     taux_tva: Decimal) -> dict:
    lignes = (actes or []) + (produits or [])
    sous_total = sum(
        (Decimal(str(line["prix"])) * Decimal(str(line.get("quantite", 1))) for line in lignes),
        Decimal("0.000"),
    )
    apres_remise = sous_total * (Decimal("100") - remise_globale_pct) / Decimal("100")
    montant_tva = apres_remise * taux_tva
    total_ttc = apres_remise + montant_tva
    return {
        "sous_total": sous_total.quantize(Decimal("0.001")),
        "montant_tva": montant_tva.quantize(Decimal("0.001")),
        "total_ttc": total_ttc.quantize(Decimal("0.001")),
    }


def _resolve_service_clinic(clinic_id: int | None) -> int:
    if clinic_id and clinic_id > 0:
        return int(clinic_id)
    settings = get_settings()
    if settings.env in {"test", "development"}:
        return int(settings.clinic_id or 1)
    raise ValueError("Contexte clinique obligatoire")


async def create_facture(data: dict, created_by: int, db, clinic_id: int | None = None) -> Facture:
    clinic_id = _resolve_service_clinic(clinic_id)
    result = await db.execute(select(Patient).where(
        Patient.id == data["patient_id"], Patient.clinic_id == clinic_id,
    ))
    patient = result.scalar_one_or_none()
    if not patient:
        raise ValueError("Patient non trouvé")

    taux_tva = Decimal(str(data.get("taux_tva", "0.190")))
    remise = Decimal(str(data.get("remise_globale_pct", "0.00")))
    actes_json = _json_lines(data.get("actes", []))
    produits_json = _json_lines(data.get("produits", []))
    totals = _compute_totals(actes_json, produits_json, remise, taux_tva)

    # _generate_numero_facture() compte les factures existantes sans
    # verrou : deux créations simultanées peuvent lire le même compte et
    # obtenir le même numéro. La contrainte unique sur numero_facture
    # (models/database.py) fait échouer l'insertion dans ce cas — on
    # regénère et on réessaie plutôt que de verrouiller une table entière
    # (portable SQLite/Postgres, contrairement à un with_for_update sur
    # un COUNT qui ne verrouille aucune ligne réelle).
    max_essais = 5
    for tentative in range(max_essais):
        facture = Facture(
            clinic_id=clinic_id,
            patient_id=data["patient_id"],
            rdv_id=data.get("rdv_id"),
            numero_facture=await _generate_numero_facture(db),
            date_emission=data.get("date_emission", date.today()),
            date_echeance=data.get("date_echeance"),
            actes=actes_json,
            produits=produits_json,
            taux_tva=taux_tva,
            remise_globale_pct=remise,
            notes=data.get("notes"),
            created_by=created_by,
            statut=StatutFacture.BROUILLON.value,
            **totals,
        )
        db.add(facture)
        try:
            await db.flush()
            return facture
        except IntegrityError:
            await db.rollback()
            if tentative == max_essais - 1:
                raise ValueError("Impossible de générer un numéro de facture unique, réessayez")
            continue


async def marquer_payee(facture_id: int, mode_paiement: str, db, clinic_id: int | None = None) -> dict:
    clinic_id = _resolve_service_clinic(clinic_id)
    result = await db.execute(select(Facture).where(
        Facture.id == facture_id, Facture.clinic_id == clinic_id,
    ))
    facture = result.scalar_one_or_none()
    if not facture:
        raise ValueError("Facture non trouvée")
    if facture.statut == StatutFacture.PAYEE.value:
        raise ValueError("Cette facture est déjà marquée comme payée")
    if facture.statut == StatutFacture.ANNULEE.value:
        raise ValueError("Impossible de payer une facture annulée")

    facture.statut = StatutFacture.PAYEE.value
    facture.mode_paiement = mode_paiement
    await db.flush()

    patient_result = await db.execute(select(Patient).where(
        Patient.id == facture.patient_id, Patient.clinic_id == clinic_id,
    ))
    patient = patient_result.scalar_one_or_none()

    commission = None
    if patient and patient.commercial_id:
        commission = await create_commission(
            commercial_id=patient.commercial_id, patient_id=patient.id,
            facture_id=facture.id, montant_ca=facture.total_ttc, db=db,
            clinic_id=facture.clinic_id,
        )

    points_gagnes = int(facture.total_ttc // POINTS_PAR_UNITE)
    if points_gagnes > 0:
        await add_points(
            patient_id=facture.patient_id, points=points_gagnes,
            motif=f"Facture {facture.numero_facture}", db=db,
            reference_id=facture.id, reference_type="facture",
            clinic_id=facture.clinic_id,
        )

    return {"facture": facture, "commission": commission, "points_gagnes": points_gagnes}


async def annuler_facture(facture_id: int, motif: str, db, clinic_id: int | None = None) -> Facture:
    clinic_id = _resolve_service_clinic(clinic_id)
    result = await db.execute(select(Facture).where(
        Facture.id == facture_id, Facture.clinic_id == clinic_id,
    ))
    facture = result.scalar_one_or_none()
    if not facture:
        raise ValueError("Facture non trouvée")
    if facture.statut == StatutFacture.PAYEE.value:
        raise ValueError("Impossible d'annuler une facture déjà payée — émettre un avoir")

    facture.statut = StatutFacture.ANNULEE.value
    facture.notes = f"{facture.notes or ''}\n[ANNULÉE] {motif}".strip()
    await db.flush()
    return facture


async def list_factures(db, clinic_id: int | None = None, patient_id: Optional[int] = None, statut: Optional[str] = None,
                         skip: int = 0, limit: int = 100) -> tuple[list[Facture], int]:
    clinic_id = _resolve_service_clinic(clinic_id)
    query = select(Facture).where(Facture.clinic_id == clinic_id)
    count_query = select(func.count(Facture.id)).where(Facture.clinic_id == clinic_id)
    if patient_id:
        query = query.where(Facture.patient_id == patient_id)
        count_query = count_query.where(Facture.patient_id == patient_id)
    if statut:
        query = query.where(Facture.statut == statut)
        count_query = count_query.where(Facture.statut == statut)

    total = (await db.execute(count_query)).scalar_one()
    result = await db.execute(
        query.order_by(Facture.created_at.desc()).offset(skip).limit(limit)
    )
    return list(result.scalars().all()), total
