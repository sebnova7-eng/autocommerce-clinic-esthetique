"""AutoCommerce Clinic — API Factures"""
from datetime import date
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_db
from middleware.clinic_rbac import require_role
from models.database import RoleEnum
from services.factures import create_facture, marquer_payee, annuler_facture, list_factures
from services.pdf_generator import generate_invoice_pdf
from sqlalchemy import select
from models.database import Facture, Patient, AuditLogFinancial

router = APIRouter(prefix="/factures", tags=["factures"])


class LigneFacture(BaseModel):
    description: str
    prix: Decimal
    quantite: int = 1


class FactureCreate(BaseModel):
    patient_id: int
    rdv_id: Optional[int] = None
    actes: list[LigneFacture] = []
    produits: list[LigneFacture] = []
    taux_tva: Decimal = Decimal("0.190")
    remise_globale_pct: Decimal = Decimal("0.00")
    date_echeance: Optional[date] = None
    notes: Optional[str] = None


class PaiementRequest(BaseModel):
    mode_paiement: str


class AnnulationRequest(BaseModel):
    motif: str


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_facture_route(
    payload: FactureCreate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role(RoleEnum.DIRECTRICE, RoleEnum.ASSISTANTE, RoleEnum.ADMIN)),
):
    data = payload.model_dump()
    data["actes"] = [a for a in data["actes"]]
    data["produits"] = [p for p in data["produits"]]
    try:
        facture = await create_facture(
            data, created_by=current_user["id"], db=db,
            clinic_id=current_user["clinic_id"],
        )
        # Log Audit Financier
        audit = AuditLogFinancial(
            entite_type="facture",
            clinic_id=current_user["clinic_id"],
            entite_id=facture.id,
            action="creation",
            valeur_apres={"total_ttc": float(facture.total_ttc), "statut": facture.statut},
            modifie_par_id=current_user["id"]
        )
        db.add(audit)
        await db.commit()
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    return {"id": facture.id, "numero_facture": facture.numero_facture, "total_ttc": facture.total_ttc,
            "statut": facture.statut}


@router.get("")
async def list_factures_route(
    response: Response,
    patient_id: Optional[int] = Query(None),
    statut: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role(RoleEnum.DIRECTRICE, RoleEnum.MEDECIN, RoleEnum.ESTHETICIENNE,
                                       RoleEnum.ASSISTANTE, RoleEnum.ADMIN)),
):
    # Auparavant : tout l'historique des factures chargé en mémoire à
    # chaque appel, sans limite. skip/limit pagine désormais la requête;
    # le total réel (pas juste la taille de la page) est renvoyé dans
    # X-Total-Count pour ne pas casser les appelants existants qui
    # attendent un simple tableau.
    factures, total = await list_factures(
        db, clinic_id=current_user["clinic_id"], patient_id=patient_id,
        statut=statut, skip=skip, limit=limit,
    )
    response.headers["X-Total-Count"] = str(total)
    return [{"id": f.id, "numero_facture": f.numero_facture, "patient_id": f.patient_id,
             "total_ttc": f.total_ttc, "statut": f.statut, "date_emission": f.date_emission} for f in factures]


@router.post("/{facture_id}/payer")
async def payer_facture_route(
    facture_id: int,
    payload: PaiementRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role(RoleEnum.DIRECTRICE, RoleEnum.ASSISTANTE, RoleEnum.ADMIN)),
):
    try:
        result = await marquer_payee(
            facture_id, payload.mode_paiement, db,
            clinic_id=current_user["clinic_id"],
        )
        # Log Audit Financier
        audit = AuditLogFinancial(
            entite_type="facture",
            clinic_id=current_user["clinic_id"],
            entite_id=facture_id,
            action="paiement",
            valeur_apres={"mode_paiement": payload.mode_paiement, "statut": result["facture"].statut},
            modifie_par_id=current_user["id"]
        )
        db.add(audit)
        await db.commit()
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return {
        "statut": result["facture"].statut,
        "commission_generee": result["commission"] is not None,
        "points_gagnes": result["points_gagnes"],
    }


@router.get("/audit-logs")
async def list_audit_logs(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role(RoleEnum.DIRECTRICE, RoleEnum.ADMIN)),
):
    """Liste les logs d'audit financier pour la direction."""
    from sqlalchemy.orm import joinedload
    result = await db.execute(
        select(AuditLogFinancial)
        .where(AuditLogFinancial.clinic_id == current_user["clinic_id"])
        .options(joinedload(AuditLogFinancial.modifie_par))
        .order_by(AuditLogFinancial.created_at.desc())
        .limit(100)
    )
    logs = result.scalars().all()
    return [{
        "id": log.id,
        "entite_type": log.entite_type,
        "entite_id": log.entite_id,
        "action": log.action,
        "valeur_apres": log.valeur_apres,
        "modifie_par_nom": f"{log.modifie_par.prenom} {log.modifie_par.nom}",
        "created_at": log.created_at
    } for log in logs]

@router.post("/{facture_id}/annuler")
async def annuler_facture_route(
    facture_id: int,
    payload: AnnulationRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role(RoleEnum.DIRECTRICE, RoleEnum.ADMIN)),
):
    try:
        facture = await annuler_facture(
            facture_id, payload.motif, db,
            clinic_id=current_user["clinic_id"],
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return {"id": facture.id, "statut": facture.statut}


@router.get("/{facture_id}/pdf")
async def get_facture_pdf(
    facture_id: int,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role(RoleEnum.DIRECTRICE, RoleEnum.ASSISTANTE, RoleEnum.ADMIN)),
):
    """Génère et retourne le PDF d'une facture."""
    result = await db.execute(select(Facture).where(
        Facture.id == facture_id,
        Facture.clinic_id == current_user["clinic_id"],
    ))
    facture = result.scalar_one_or_none()
    if not facture:
        raise HTTPException(status_code=404, detail="Facture non trouvée")
    
    patient_res = await db.execute(select(Patient).where(
        Patient.id == facture.patient_id,
        Patient.clinic_id == current_user["clinic_id"],
    ))
    patient = patient_res.scalar_one()
    
    from services.branding import get_branding_context
    branding = await get_branding_context(db, clinic_id=current_user["clinic_id"])
    
    pdf_bytes = await generate_invoice_pdf(facture, patient, branding)
    
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="facture_{facture.numero_facture}.pdf"'},
    )


@router.get("/devis/{facture_id}/pdf")
async def get_devis_pdf(
    facture_id: int,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role(RoleEnum.DIRECTRICE, RoleEnum.ASSISTANTE, RoleEnum.ADMIN)),
):
    """Génère et retourne le PDF d'un devis (même logique que facture)."""
    return await get_facture_pdf(facture_id, db, current_user)
