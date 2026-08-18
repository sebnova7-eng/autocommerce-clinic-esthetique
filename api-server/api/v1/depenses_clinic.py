"""
AutoCommerce Clinic — API Dépenses & Scan Facture IA
"""

from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, extract

from models.database import (
    Depense, CategorieDepense, RoleEnum,
)
from api.deps import get_db
from middleware.clinic_rbac import require_role
from services.facture_scanner import upload_facture, valider_depense
from config import get_settings

router = APIRouter(prefix="/depenses", tags=["depenses"])


# ── Schémas ────────────────────────────────────────────────

class DepenseCreate(BaseModel):
    categorie_id: Optional[int] = None
    fournisseur: Optional[str] = Field(None, max_length=200)
    titre: str = Field(..., max_length=300)
    description: Optional[str] = None
    montant_ht: Decimal = Field(default=Decimal("0.000"))
    taux_tva: Decimal = Field(default=Decimal("0.190"))
    montant_tva: Optional[Decimal] = None
    montant_ttc: Optional[Decimal] = None
    date_depense: str  # YYYY-MM-DD
    periode_comptable: Optional[str] = None
    mode_paiement: Optional[str] = Field(None, max_length=50)
    reference_paiement: Optional[str] = Field(None, max_length=100)
    notes: Optional[str] = None


class DepenseOut(BaseModel):
    id: int
    titre: str
    fournisseur: Optional[str]
    montant_ht: float
    montant_tva: float
    montant_ttc: float
    date_depense: str
    facture_scan_statut: str
    extraction_ia: Optional[dict]

    class Config:
        from_attributes = True


class ValidationRequest(BaseModel):
    corrections: Optional[dict] = None


# ── Routes ─────────────────────────────────────────────────

@router.post("", response_model=DepenseOut)
async def create_depense(
    data: DepenseCreate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role(RoleEnum.DIRECTRICE, RoleEnum.ASSISTANTE)),
):
    """Crée une dépense manuellement."""
    depense = Depense(
        clinic_id=current_user["clinic_id"],
        categorie_id=data.categorie_id,
        fournisseur=data.fournisseur,
        titre=data.titre,
        description=data.description,
        montant_ht=data.montant_ht,
        taux_tva=data.taux_tva,
        montant_tva=data.montant_tva or (data.montant_ht * data.taux_tva),
        montant_ttc=data.montant_ttc or (data.montant_ht * (Decimal("1.000") + data.taux_tva)),
        date_depense=datetime.strptime(data.date_depense, "%Y-%m-%d").date(),
        periode_comptable=datetime.strptime(data.periode_comptable or data.date_depense, "%Y-%m-%d").date(),
        mode_paiement=data.mode_paiement,
        reference_paiement=data.reference_paiement,
        notes=data.notes,
        created_by=current_user["id"],
    )
    db.add(depense)
    await db.flush()
    return DepenseOut(
        id=depense.id,
        titre=depense.titre,
        fournisseur=depense.fournisseur,
        montant_ht=float(depense.montant_ht),
        montant_tva=float(depense.montant_tva),
        montant_ttc=float(depense.montant_ttc),
        date_depense=depense.date_depense.isoformat(),
        facture_scan_statut=depense.facture_scan_statut,
        extraction_ia=depense.extraction_ia,
    )


@router.post("/scan", response_model=DepenseOut)
async def scan_facture(
    fournisseur: Optional[str] = None,
    titre: Optional[str] = None,
    date_depense: Optional[str] = None,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role(RoleEnum.DIRECTRICE, RoleEnum.ASSISTANTE)),
):
    """Upload + scan IA d'une facture.
    Crée d'abord la dépense, puis lance l'extraction IA via Celery.
    """
    # Créer dépense minimale
    depense = Depense(
        clinic_id=current_user["clinic_id"],
        fournisseur=fournisseur or "À déterminer (IA)",
        titre=titre or f"Facture scannée {datetime.utcnow().strftime('%d/%m/%Y')}",
        date_depense=datetime.strptime(date_depense, "%Y-%m-%d").date() if date_depense else date.today(),
        periode_comptable=datetime.strptime(date_depense, "%Y-%m-%d").date() if date_depense else date.today(),
        created_by=current_user["id"],
    )
    db.add(depense)
    await db.flush()

    # Upload fichier : limite avant écriture et validation MIME côté serveur.
    settings = get_settings()
    max_bytes = settings.max_invoice_upload_size_mb * 1024 * 1024
    file_bytes = await file.read(max_bytes + 1)
    if len(file_bytes) > max_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"Facture trop volumineuse (maximum {settings.max_invoice_upload_size_mb} Mo)",
        )
    try:
        await upload_facture(
            depense.id, file_bytes, file.content_type or "application/octet-stream",
            db, clinic_id=current_user["clinic_id"],
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return DepenseOut(
        id=depense.id,
        titre=depense.titre,
        fournisseur=depense.fournisseur,
        montant_ht=float(depense.montant_ht),
        montant_tva=float(depense.montant_tva),
        montant_ttc=float(depense.montant_ttc),
        date_depense=depense.date_depense.isoformat(),
        facture_scan_statut=depense.facture_scan_statut,
        extraction_ia=depense.extraction_ia,
    )


@router.get("", response_model=List[DepenseOut])
async def list_depenses(
    periode: Optional[str] = Query(None, description="YYYY-MM"),
    categorie: Optional[int] = Query(None),
    statut: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role(RoleEnum.DIRECTRICE, RoleEnum.ASSISTANTE)),
):
    """Liste les dépenses avec filtres."""
    query = select(Depense).where(Depense.clinic_id == current_user["clinic_id"])

    if periode:
        year, month = map(int, periode.split("-"))
        query = query.where(
            extract("year", Depense.date_depense) == year,
            extract("month", Depense.date_depense) == month,
        )
    if categorie:
        query = query.where(Depense.categorie_id == categorie)
    if statut:
        query = query.where(Depense.facture_scan_statut == statut)

    query = query.order_by(Depense.date_depense.desc())
    result = await db.execute(query)
    depenses = result.scalars().all()

    return [
        DepenseOut(
            id=d.id,
            titre=d.titre,
            fournisseur=d.fournisseur,
            montant_ht=float(d.montant_ht),
            montant_tva=float(d.montant_tva),
            montant_ttc=float(d.montant_ttc),
            date_depense=d.date_depense.isoformat(),
            facture_scan_statut=d.facture_scan_statut,
            extraction_ia=d.extraction_ia,
        )
        for d in depenses
    ]


@router.patch("/{depense_id}/valider", response_model=DepenseOut)
async def valider_depense_route(
    depense_id: int,
    data: ValidationRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role(RoleEnum.DIRECTRICE)),
):
    """Valide une dépense scannée avec corrections."""
    depense, medicaments = await valider_depense(
        depense_id, current_user["id"], data.corrections, db,
        clinic_id=current_user["clinic_id"],
    )

    response = DepenseOut(
        id=depense.id,
        titre=depense.titre,
        fournisseur=depense.fournisseur,
        montant_ht=float(depense.montant_ht),
        montant_tva=float(depense.montant_tva),
        montant_ttc=float(depense.montant_ttc),
        date_depense=depense.date_depense.isoformat(),
        facture_scan_statut=depense.facture_scan_statut,
        extraction_ia=depense.extraction_ia,
    )

    # Si médicaments détectés, ajouter info
    if medicaments:
        response.__dict__["medicaments_detectes"] = len(medicaments)

    return response


@router.get("/stats")
async def depenses_stats(
    periode: str = Query(..., description="YYYY-MM", pattern=r"^\d{4}-\d{2}$"),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role(RoleEnum.DIRECTRICE, RoleEnum.ASSISTANTE)),
):
    """Statistiques dépenses par période."""
    try:
        year, month = map(int, periode.split("-"))
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Format de période invalide. Attendu: YYYY-MM, reçu: {periode}")

    result = await db.execute(
        select(
            func.count(Depense.id).label("nb_depenses"),
            func.sum(Depense.montant_ttc).label("total_ttc"),
            func.sum(Depense.montant_ht).label("total_ht"),
        )
        .where(Depense.clinic_id == current_user["clinic_id"])
        .where(extract("year", Depense.date_depense) == year)
        .where(extract("month", Depense.date_depense) == month)
    )
    row = result.one()

    return {
        "periode": periode,
        "nb_depenses": row.nb_depenses or 0,
        "total_ht": float(row.total_ht or 0),
        "total_ttc": float(row.total_ttc or 0),
    }


@router.get("/budget-vs-reel")
async def budget_vs_reel(
    mois: str = Query(..., description="YYYY-MM", pattern=r"^\d{4}-\d{2}$"),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role(RoleEnum.DIRECTRICE)),
):
    """Comparaison budget vs réel par catégorie."""
    try:
        year, month = map(int, mois.split("-"))
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Format de mois invalide. Attendu: YYYY-MM, reçu: {mois}")

    # Budgets
    cat_result = await db.execute(select(CategorieDepense).where(CategorieDepense.clinic_id == current_user["clinic_id"]))
    categories = cat_result.scalars().all()

    # Dépenses réelles
    dep_result = await db.execute(
        select(
            Depense.categorie_id,
            func.sum(Depense.montant_ttc).label("total"),
        )
        .where(Depense.clinic_id == current_user["clinic_id"])
        .where(extract("year", Depense.date_depense) == year)
        .where(extract("month", Depense.date_depense) == month)
        .group_by(Depense.categorie_id)
    )
    depenses_par_cat = {row.categorie_id: float(row.total) for row in dep_result.all()}

    data = []
    for cat in categories:
        reel = depenses_par_cat.get(cat.id, 0)
        budget = float(cat.budget_mensuel) if cat.budget_mensuel else 0
        data.append({
            "categorie": cat.nom,
            "code": cat.code,
            "budget": budget,
            "reel": reel,
            "ecart": reel - budget,
            "couleur": cat.couleur,
        })

    return {"mois": mois, "categories": data}
