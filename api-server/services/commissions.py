"""
AutoCommerce Clinic — Service Commissions

Une commission est calculée automatiquement au paiement d'une
facture (voir services/factures.py) puis validée/payée par la
direction.
"""
from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import COMMISSION_VALIDATION_SEUIL
from models.database import Commission, StatutCommission, Utilisateur


async def create_commission(commercial_id: int, patient_id: int, facture_id: int,
                             montant_ca: Decimal, db: AsyncSession, clinic_id: int = 1) -> Optional[Commission]:
    """Retourne None si le commercial n'a pas de taux de commission (0%) —
    pas la peine de créer une ligne à 0 DT."""
    result = await db.execute(select(Utilisateur).where(Utilisateur.id == commercial_id))
    commercial = result.scalar_one_or_none()
    if not commercial or commercial.taux_commission <= 0:
        return None

    montant_commission = (montant_ca * commercial.taux_commission / Decimal("100")).quantize(Decimal("0.001"))

    commission = Commission(
        clinic_id=clinic_id, commercial_id=commercial_id, patient_id=patient_id, facture_id=facture_id,
        montant_ca=montant_ca, taux_commission=commercial.taux_commission,
        montant_commission=montant_commission,
        statut=StatutCommission.EN_ATTENTE.value,
        periode_mois=date.today().replace(day=1),
    )
    db.add(commission)
    await db.flush()
    return commission


async def valider_commission(commission_id: int, validateur_id: int, db: AsyncSession) -> Commission:
    """Valide une commission. Au-delà de COMMISSION_VALIDATION_SEUIL (500 DT),
    deux validations par des personnes distinctes sont requises avant de
    passer à VALIDEE — une seule ne suffit pas."""
    result = await db.execute(select(Commission).where(Commission.id == commission_id))
    commission = result.scalar_one_or_none()
    if not commission:
        raise ValueError("Commission non trouvée")

    depasse_seuil = commission.montant_commission > Decimal(str(COMMISSION_VALIDATION_SEUIL))

    if commission.statut == StatutCommission.EN_ATTENTE.value:
        if depasse_seuil:
            commission.statut = StatutCommission.VALIDATION_PARTIELLE.value
            commission.validee_par_id = validateur_id
            commission.validated_at = datetime.utcnow()
        else:
            commission.statut = StatutCommission.VALIDEE.value
            commission.validee_par_id = validateur_id
            commission.validated_at = datetime.utcnow()
    elif commission.statut == StatutCommission.VALIDATION_PARTIELLE.value:
        if validateur_id == commission.validee_par_id:
            raise ValueError("La deuxième validation doit être faite par une personne différente")
        commission.statut = StatutCommission.VALIDEE.value
        commission.validee_par_id_2 = validateur_id
        commission.validated_at_2 = datetime.utcnow()
    else:
        raise ValueError(f"Statut invalide pour validation : {commission.statut}")

    await db.flush()
    return commission


async def marquer_payee(commission_id: int, date_paiement: date, db: AsyncSession) -> Commission:
    result = await db.execute(select(Commission).where(Commission.id == commission_id))
    commission = result.scalar_one_or_none()
    if not commission:
        raise ValueError("Commission non trouvée")
    if commission.statut == StatutCommission.PAYEE.value:
        return commission
    if commission.statut != StatutCommission.VALIDEE.value:
        raise ValueError("La commission doit être validée avant paiement")

    commission.statut = StatutCommission.PAYEE.value
    commission.date_paiement = date_paiement
    await db.flush()
    return commission


async def list_commissions(current_user: dict, db: AsyncSession,
                            periode_mois: Optional[date] = None) -> list[Commission]:
    query = select(Commission)
    if current_user.get("role") == "commercial":
        query = query.where(Commission.commercial_id == current_user.get("id"))
    if periode_mois:
        query = query.where(Commission.periode_mois == periode_mois)
    result = await db.execute(query.order_by(Commission.created_at.desc()))
    return list(result.scalars().all())


async def total_du_par_commercial(commercial_id: int, db: AsyncSession) -> Decimal:
    result = await db.execute(
        select(Commission).where(
            Commission.commercial_id == commercial_id,
            Commission.statut != StatutCommission.PAYEE.value,
        )
    )
    commissions = result.scalars().all()
    return sum((c.montant_commission for c in commissions), Decimal("0.000"))
