"""
AutoCommerce Clinic — Gestion stock injectables
Scan, traçabilité, alertes, utilisation
"""

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import List, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func

from models.database import (
    LotInjectable,
    ProduitInjectable,
    UtilisationLot,
    StatutLot,
    Utilisateur,
)
from services.qr_injectable import decode_scan
from services.clinic_settings import _resolve_clinic_id


def _resolve_usage_datetime(date_injection: Optional[datetime]) -> datetime:
    """Garantit une date d'utilisation non nulle pour la traçabilité.

    Correctif Bug #3 (audit): quand le front n'envoie pas de
    ``date_injection`` explicite, l'enregistrement doit prendre la date
    UTC courante afin de satisfaire la contrainte NOT NULL sur
    ``utilisations_lot.date_utilisation`` et préserver la traçabilité
    temporelle.
    """
    return date_injection if date_injection is not None else datetime.utcnow()


# ── Dataclasses ────────────────────────────────────────────

@dataclass
class LotDetail:
    lot_id: int
    produit_nom: str
    fabricant: Optional[str]
    numero_lot: str
    quantite_restante: Decimal
    unite: str
    date_expiration: date
    statut: str
    jours_avant_expiration: int
    stock_minimum: Decimal
    stock_alerte: Decimal


@dataclass
class StockAlert:
    niveau: str  # "rouge" | "orange" | "vert"
    produit_nom: str
    numero_lot: str
    message: str
    lot_id: int


# ── Scan & recherche lot ─────────────────────────────────

async def get_lot_by_scan(code_str: str, db: AsyncSession) -> LotDetail:
    """Recherche un lot par scan (QR JSON ou Code 128)."""
    decoded = decode_scan(code_str)

    if decoded["type"] == "qr_json":
        lot_id = decoded["data"].get("lot_id")
        if not lot_id:
            raise ValueError("QR code sans lot_id")
        result = await db.execute(
            select(LotInjectable, ProduitInjectable)
            .join(ProduitInjectable, LotInjectable.produit_id == ProduitInjectable.id)
            .where(LotInjectable.id == lot_id)
        )
    elif decoded["type"] == "barcode":
        numero_lot = decoded["numero_lot"]
        result = await db.execute(
            select(LotInjectable, ProduitInjectable)
            .join(ProduitInjectable, LotInjectable.produit_id == ProduitInjectable.id)
            .where(LotInjectable.numero_lot == numero_lot)
        )
    else:
        raise ValueError(f"Format de scan non reconnu : {decoded.get('raw', code_str)}")

    row = result.first()
    if not row:
        raise ValueError("Lot non trouvé")

    lot, produit = row
    jours = (lot.date_expiration - date.today()).days

    return LotDetail(
        lot_id=lot.id,
        produit_nom=produit.nom,
        fabricant=produit.fabricant,
        numero_lot=lot.numero_lot,
        quantite_restante=lot.quantite_restante,
        unite=produit.unite,
        date_expiration=lot.date_expiration,
        statut=lot.statut,
        jours_avant_expiration=jours,
        stock_minimum=produit.stock_minimum,
        stock_alerte=produit.stock_alerte,
    )


# ── Enregistrement utilisation ────────────────────────────

async def register_usage(
    lot_id: int,
    dossier_id: Optional[int],
    patient_id: int,
    praticien_id: int,
    quantite: Decimal,
    unite: str,
    db: AsyncSession,
    type_injection: Optional[str] = None,
    date_injection: Optional[datetime] = None,
    notes: Optional[str] = None,
) -> UtilisationLot:
    """Débite le stock d'un lot et crée une utilisation.

    Vérifie :
    - Lot existe et disponible
    - Quantité suffisante (avec verrou pessimiste anti race-condition)
    - Lot non expiré
    - Quantité strictement positive

    Correctif Bug #1 (audit) :
    - Cast strict Decimal(str(quantite)) pour éviter la propagation d'un
      float depuis Pydantic (perte de précision arithmétique).
    - Verrou pessimiste ``SELECT ... FOR UPDATE`` sur la ligne du lot
      pour sérialiser les décrémentations concurrentes.
    - Décrémentation via nouvelle valeur ``Decimal`` recalculée (pas
      d'opérateur ``-=`` sur un attribut ORM potentiellement partagé).
    - Ordre transactionnel sûr : mutation du lot -> flush -> ajout de
      l'UtilisationLot -> flush -> refresh, avec rollback implicite
      via l'exception si le flush échoue (rien n'est persisté à moitié).
    - Vérification post-décrémentation que ``quantite_restante >= 0``.
    """
    # ── 1. Validation stricte des entrées ─────────────────────
    try:
        quantite = Decimal(str(quantite))
    except (ArithmeticError, ValueError, TypeError) as exc:
        raise ValueError(f"Quantité invalide : {quantite!r}") from exc

    if quantite <= 0:
        raise ValueError(
            f"Quantité doit être strictement positive (reçu : {quantite})"
        )

    # ── 2. Chargement du lot avec verrou pessimiste ───────────
    # ``with_for_update()`` empêche deux appels concurrents de lire
    # simultanément la même quantité_restante et de la décrémenter
    # tous les deux (double-spend). La ligne est verrouillée jusqu'à
    # la fin de la transaction.
    result = await db.execute(
        select(LotInjectable, ProduitInjectable)
        .join(ProduitInjectable, LotInjectable.produit_id == ProduitInjectable.id)
        .where(LotInjectable.id == lot_id)
        .with_for_update(of=LotInjectable)
    )
    row = result.first()
    if not row:
        raise ValueError(f"Lot {lot_id} non trouvé")

    lot, produit = row

    # ── 3. Vérifications métier ───────────────────────────────
    if lot.statut in (StatutLot.EPUISE.value, StatutLot.EXPIRE.value, StatutLot.RETIRE.value):
        raise ValueError(f"Lot indisponible (statut: {lot.statut})")

    if lot.date_expiration < date.today():
        lot.statut = StatutLot.EXPIRE.value
        await db.flush()
        raise ValueError("Lot expiré — utilisation impossible")

    # Cast défensif de la valeur ORM (peut arriver en float sur certains
    # dialectes ou après un refresh partiel).
    stock_actuel = Decimal(str(lot.quantite_restante))

    if stock_actuel < quantite:
        raise ValueError(
            f"Stock insuffisant : {stock_actuel} {produit.unite} disponible, "
            f"{quantite} {unite} demandé"
        )

    # ── 4. Débit atomique ─────────────────────────────────────
    nouveau_stock = stock_actuel - quantite

    # Garde-fou : ne doit jamais descendre en négatif après le check
    # ci-dessus, mais on blinde en cas de race condition résiduelle.
    if nouveau_stock < 0:
        raise ValueError(
            f"Stock insuffisant après vérification concurrente : "
            f"{stock_actuel} - {quantite} = {nouveau_stock}"
        )

    lot.quantite_restante = nouveau_stock

    # Mise à jour du statut selon le nouveau niveau de stock
    if nouveau_stock == 0:
        lot.quantite_restante = Decimal("0.00")
        lot.statut = StatutLot.EPUISE.value
    elif nouveau_stock <= Decimal(str(produit.stock_minimum)):
        lot.statut = StatutLot.QUARANTAINE.value

    # Flush intermédiaire pour verrouiller la décrémentation en base
    # AVANT de créer l'utilisation. Si ce flush échoue (contrainte,
    # déconnexion), l'UtilisationLot ne sera jamais créé.
    await db.flush()

    # ── 5. Création de l'utilisation ──────────────────────────
    usage_datetime = _resolve_usage_datetime(date_injection)

    # Calcul de la date de prochaine injection basée sur la durée d'effet du produit
    prochaine_date = None
    if produit.duree_effet_jours and produit.duree_effet_jours > 0:
        prochaine_date = (usage_datetime + timedelta(days=produit.duree_effet_jours)).date()

    utilisation = UtilisationLot(
        clinic_id=lot.clinic_id,
        lot_id=lot_id,
        dossier_id=dossier_id,
        patient_id=patient_id,
        praticien_id=praticien_id,
        date_utilisation=usage_datetime,
        quantite_utilisee=quantite,
        unite=unite,
        type_injection=type_injection,
        notes=notes,
        prochaine_injection_date=prochaine_date,
        prochaine_injection_envoyee=False,
    )
    db.add(utilisation)
    await db.flush()
    await db.refresh(utilisation)

    # ── 6. Alertes post-utilisation ───────────────────────────
    await _check_single_lot_alert(lot, produit, db)

    return utilisation


async def _check_single_lot_alert(lot: LotInjectable, produit: ProduitInjectable, db: AsyncSession):
    """Vérifie si une alerte doit être déclenchée après utilisation."""
    # Si stock très bas, on pourrait déclencher une tâche Celery ici
    pass


# ── Alertes stock ──────────────────────────────────────────

async def check_stock_alerts(db: AsyncSession, clinic_id: Optional[int] = None) -> List[StockAlert]:
    """Retourne toutes les alertes stock.

    ROUGE : stock = 0 OU lot expiré
    ORANGE : stock < minimum OU expire dans < 30j
    VERT : expire dans < 60j (info)
    """
    clinic_id = _resolve_clinic_id(clinic_id)
    alerts: List[StockAlert] = []
    today = date.today()

    result = await db.execute(
        select(LotInjectable, ProduitInjectable)
        .join(ProduitInjectable, LotInjectable.produit_id == ProduitInjectable.id)
        .where(LotInjectable.clinic_id == clinic_id)
        .where(ProduitInjectable.clinic_id == clinic_id)
        .where(LotInjectable.statut.in_([
            StatutLot.DISPONIBLE.value,
            StatutLot.QUARANTAINE.value,
        ]))
    )

    for lot, produit in result.all():
        jours = (lot.date_expiration - today).days

        # ROUGE
        if lot.quantite_restante <= 0 or jours < 0:
            alerts.append(StockAlert(
                niveau="rouge",
                produit_nom=produit.nom,
                numero_lot=lot.numero_lot,
                message=f"RUPTURE — {lot.quantite_restante} {produit.unite} restant" if lot.quantite_restante <= 0 else f"EXPIRÉ depuis {abs(jours)} jours",
                lot_id=lot.id,
            ))
        # ORANGE
        elif lot.quantite_restante <= produit.stock_minimum or jours <= 30:
            alerts.append(StockAlert(
                niveau="orange",
                produit_nom=produit.nom,
                numero_lot=lot.numero_lot,
                message=f"{lot.quantite_restante} {produit.unite} restant — expire dans {jours}j" if jours <= 30 else f"Stock bas : {lot.quantite_restante} {produit.unite}",
                lot_id=lot.id,
            ))
        # VERT (info)
        elif jours <= 60:
            alerts.append(StockAlert(
                niveau="vert",
                produit_nom=produit.nom,
                numero_lot=lot.numero_lot,
                message=f"Expire dans {jours} jours",
                lot_id=lot.id,
            ))

    return alerts


# ── Traçabilité patient ───────────────────────────────────

async def get_tracabilite_patient(patient_id: int, db: AsyncSession) -> List[dict]:
    """Retourne l'historique complet des injectables utilisés sur une patiente."""
    result = await db.execute(
        select(
            UtilisationLot,
            LotInjectable,
            ProduitInjectable,
            Utilisateur,
        )
        .join(LotInjectable, UtilisationLot.lot_id == LotInjectable.id)
        .join(ProduitInjectable, LotInjectable.produit_id == ProduitInjectable.id)
        .join(Utilisateur, UtilisationLot.praticien_id == Utilisateur.id)
        .where(UtilisationLot.patient_id == patient_id)
        .order_by(UtilisationLot.date_utilisation.desc())
    )

    history = []
    for util, lot, prod, prat in result.all():
        history.append({
            "date": util.date_utilisation.isoformat(),
            "produit": prod.nom,
            "fabricant": prod.fabricant,
            "numero_lot": lot.numero_lot,
            "quantite": float(util.quantite_utilisee),
            "unite": util.unite,
            "praticien": f"{prat.prenom} {prat.nom}",
            "notes": util.notes,
        })

    return history


# ── Dashboard stock ────────────────────────────────────────

async def get_stock_dashboard(db: AsyncSession) -> dict:
    """Retourne le tableau de bord stock complet."""
    # Total par produit
    result = await db.execute(
        select(
            ProduitInjectable.id,
            ProduitInjectable.nom,
            ProduitInjectable.categorie,
            ProduitInjectable.unite,
            ProduitInjectable.stock_minimum,
            func.coalesce(func.sum(LotInjectable.quantite_restante), Decimal("0.00")).label("total_restant"),
            func.count(LotInjectable.id).label("nb_lots"),
        )
        .outerjoin(LotInjectable, and_(
            LotInjectable.produit_id == ProduitInjectable.id,
            LotInjectable.statut.in_([StatutLot.DISPONIBLE.value, StatutLot.QUARANTAINE.value]),
        ))
        .where(ProduitInjectable.is_active)
        .group_by(ProduitInjectable.id)
    )

    produits = []
    for row in result.all():
        total = row.total_restant or Decimal("0.00")
        statut = "ok"
        if total <= 0:
            statut = "rupture"
        elif total <= row.stock_minimum:
            statut = "alerte"

        produits.append({
            "produit_id": row.id,
            "nom": row.nom,
            "categorie": row.categorie,
            "unite": row.unite,
            "stock_total": float(total),
            "stock_minimum": float(row.stock_minimum),
            "nb_lots_actifs": row.nb_lots,
            "statut": statut,
        })

    # Alertes
    alerts = await check_stock_alerts(db)

    return {
        "produits": produits,
        "alertes": {
            "rouge": [a for a in alerts if a.niveau == "rouge"],
            "orange": [a for a in alerts if a.niveau == "orange"],
            "vert": [a for a in alerts if a.niveau == "vert"],
        },
        "total_alertes": len(alerts),
    }
