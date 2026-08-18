"""
AutoCommerce Clinic — Service Téléconsultation
Génération de liens visio et gestion d'état.
"""
import uuid
from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from models.database import Teleconsultation, RendezVous
from config import get_settings

class TeleconsultationService:
    @staticmethod
    async def creer_pour_rdv(db: AsyncSession, rdv_id: int, clinic_id: int = 1) -> Optional[Teleconsultation]:
        settings = get_settings()
        if settings.env == "production" and not settings.teleconsultation_enabled:
            raise RuntimeError("Téléconsultation désactivée par la configuration de déploiement")
        # Vérifier si le RDV existe
        stmt = select(RendezVous).where(RendezVous.id == rdv_id, RendezVous.clinic_id == clinic_id)
        result = await db.execute(stmt)
        rdv = result.scalar_one_or_none()
        if not rdv:
            return None
            
        # Vérifier si une téléconsultation existe déjà
        stmt_tc = select(Teleconsultation).where(
            Teleconsultation.rdv_id == rdv_id,
            Teleconsultation.clinic_id == clinic_id,
        )
        res_tc = await db.execute(stmt_tc)
        existing = res_tc.scalar_one_or_none()
        if existing:
            return existing
            
        # Générer un lien Jitsi unique
        room_name = f"Clinic-{clinic_id}-RDV-{rdv_id}-{uuid.uuid4().hex[:8]}"
        lien = f"https://meet.jit.si/{room_name}"
        
        tc = Teleconsultation(
            clinic_id=clinic_id,
            rdv_id=rdv_id,
            lien_visio=lien,
            statut="planifiee"
        )
        db.add(tc)
        await db.commit()
        await db.refresh(tc)
        return tc

    @staticmethod
    async def get_by_rdv(db: AsyncSession, rdv_id: int, clinic_id: int) -> Optional[Teleconsultation]:
        stmt = select(Teleconsultation).where(
            Teleconsultation.rdv_id == rdv_id,
            Teleconsultation.clinic_id == clinic_id,
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def marquer_terminee(db: AsyncSession, tc_id: int, duree: int = None, notes: str = None, clinic_id: int | None = None) -> bool:
        stmt = select(Teleconsultation).where(Teleconsultation.id == tc_id)
        if clinic_id is not None:
            stmt = stmt.where(Teleconsultation.clinic_id == clinic_id)
        result = await db.execute(stmt)
        tc = result.scalar_one_or_none()
        if not tc:
            return False
            
        tc.statut = "terminee"
        if duree:
            tc.duree_reelle = duree
        if notes:
            tc.notes = notes
            
        await db.commit()
        return True
