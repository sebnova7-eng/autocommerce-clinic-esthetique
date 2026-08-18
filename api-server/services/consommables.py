"""
AutoCommerce Clinic — Service Gestion Stock Consommables
CRUD, mouvements de stock et alertes.
"""
from decimal import Decimal
from typing import List, Optional, Dict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from models.database import Consommable, MouvementConsommable

class ConsommableService:
    @staticmethod
    async def get_all(db: AsyncSession, clinic_id: int = 1) -> List[Consommable]:
        stmt = select(Consommable).where(
            Consommable.clinic_id == clinic_id,
            Consommable.is_active
        ).order_by(Consommable.nom)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def get_by_id(db: AsyncSession, consommable_id: int, clinic_id: int = 1) -> Optional[Consommable]:
        stmt = select(Consommable).where(
            Consommable.id == consommable_id,
            Consommable.clinic_id == clinic_id
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def create(db: AsyncSession, data: dict, clinic_id: int = 1) -> Consommable:
        consommable = Consommable(
            clinic_id=clinic_id,
            nom=data["nom"],
            categorie=data["categorie"],
            unite=data["unite"],
            stock_actuel=Decimal(str(data.get("stock_actuel", 0))),
            seuil_alerte=Decimal(str(data.get("seuil_alerte", 0))),
            stock_minimum=Decimal(str(data.get("stock_minimum", 0))),
            prix_unitaire=Decimal(str(data.get("prix_unitaire", 0))),
            fournisseur_id=data.get("fournisseur_id"),
            is_active=True
        )
        db.add(consommable)
        await db.commit()
        await db.refresh(consommable)
        return consommable

    @staticmethod
    async def update(db: AsyncSession, consommable_id: int, data: dict, clinic_id: int = 1) -> Optional[Consommable]:
        consommable = await ConsommableService.get_by_id(db, consommable_id, clinic_id)
        if not consommable:
            return None
        
        for key, value in data.items():
            if hasattr(consommable, key):
                if key in ["stock_actuel", "seuil_alerte", "stock_minimum", "prix_unitaire"]:
                    setattr(consommable, key, Decimal(str(value)))
                else:
                    setattr(consommable, key, value)
        
        await db.commit()
        await db.refresh(consommable)
        return consommable

    @staticmethod
    async def delete(db: AsyncSession, consommable_id: int, clinic_id: int = 1) -> bool:
        consommable = await ConsommableService.get_by_id(db, consommable_id, clinic_id)
        if not consommable:
            return False
        
        consommable.is_active = False
        await db.commit()
        return True

    @staticmethod
    async def add_mouvement(
        db: AsyncSession, 
        consommable_id: int, 
        type_mvt: str, 
        quantite: float, 
        utilisateur_id: int,
        motif: str = None,
        reference: str = None,
        clinic_id: int = 1
    ) -> Optional[MouvementConsommable]:
        consommable = await ConsommableService.get_by_id(db, consommable_id, clinic_id)
        if not consommable:
            return None
        
        qte_decimal = Decimal(str(quantite))

        if type_mvt == "sortie" and consommable.stock_actuel < qte_decimal:
            raise ValueError(
                f"Stock insuffisant : {consommable.stock_actuel} {consommable.unite} disponible(s), "
                f"{qte_decimal} demandé(s)"
            )

        # Créer le mouvement
        mouvement = MouvementConsommable(
            clinic_id=clinic_id,
            consommable_id=consommable_id,
            type=type_mvt,
            quantite=qte_decimal,
            utilisateur_id=utilisateur_id,
            motif=motif,
            reference=reference
        )
        db.add(mouvement)
        
        # Mettre à jour le stock
        if type_mvt == "entree":
            consommable.stock_actuel += qte_decimal
        elif type_mvt == "sortie":
            consommable.stock_actuel -= qte_decimal
            
        await db.commit()
        await db.refresh(mouvement)
        return mouvement

    @staticmethod
    async def get_alertes(db: AsyncSession, clinic_id: int = 1) -> List[Dict]:
        stmt = select(Consommable).where(
            Consommable.clinic_id == clinic_id,
            Consommable.is_active,
            Consommable.stock_actuel <= Consommable.seuil_alerte
        ).order_by(Consommable.stock_actuel)
        
        result = await db.execute(stmt)
        alertes = []
        for c in result.scalars().all():
            niveau = "critique" if c.stock_actuel <= c.stock_minimum else "alerte"
            alertes.append({
                "id": c.id,
                "nom": c.nom,
                "stock_actuel": float(c.stock_actuel),
                "seuil_alerte": float(c.seuil_alerte),
                "stock_minimum": float(c.stock_minimum),
                "niveau": niveau
            })
        return alertes
