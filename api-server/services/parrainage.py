"""
AutoCommerce Clinic — Service Parrainage
Gestion des codes et récompenses.
"""
import random
import string
from typing import List
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from models.database import Parrainage, Patient
from services import fidelite

class ParrainageService:
    @staticmethod
    def generer_code_unique(nom_patient: str) -> str:
        prefix = nom_patient[:3].upper()
        suffix = ''.join(random.choices(string.ascii_uppercase + string.digits, k=5))
        return f"{prefix}-{suffix}"

    @staticmethod
    async def get_ou_creer_code(db: AsyncSession, patient_id: int, clinic_id: int = 1) -> str:
        stmt = select(Parrainage).where(
            Parrainage.parrain_patient_id == patient_id,
            Parrainage.clinic_id == clinic_id
        )
        result = await db.execute(stmt)
        p = result.scalars().first()
        
        if p:
            return p.code_parrain
            
        # Créer un nouveau code
        stmt_pat = select(Patient).where(Patient.id == patient_id)
        res_pat = await db.execute(stmt_pat)
        patient = res_pat.scalar_one()
        
        code = ParrainageService.generer_code_unique(patient.nom)
        new_p = Parrainage(
            clinic_id=clinic_id,
            parrain_patient_id=patient_id,
            code_parrain=code,
            statut="actif"
        )
        db.add(new_p)
        await db.commit()
        return code

    @staticmethod
    async def utiliser_code(db: AsyncSession, code: str, filleul_id: int, clinic_id: int = 1) -> bool:
        # Trouver le parrainage actif avec ce code
        stmt = select(Parrainage).where(
            Parrainage.code_parrain == code,
            Parrainage.statut == "actif",
            Parrainage.clinic_id == clinic_id
        )
        result = await db.execute(stmt)
        parrainage = result.scalar_one_or_none()
        
        if not parrainage or parrainage.parrain_patient_id == filleul_id:
            return False
            
        # Associer le filleul
        parrainage.filleul_patient_id = filleul_id
        parrainage.statut = "utilise"
        parrainage.recompense_attribuee = True
        
        # Attribuer les points de fidélité (ex: 50 points chacun)
        await fidelite.add_points(
            parrainage.parrain_patient_id, 50, f"Bonus parrainage (filleul #{filleul_id})", db
        )
        await fidelite.add_points(
            filleul_id, 50, f"Bonus bienvenue parrainage (code {code})", db
        )
        
        await db.commit()
        return True

    @staticmethod
    async def get_filleuls(db: AsyncSession, parrain_id: int) -> List[Parrainage]:
        stmt = select(Parrainage).where(
            Parrainage.parrain_patient_id == parrain_id,
            Parrainage.filleul_patient_id.isnot(None)
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())
