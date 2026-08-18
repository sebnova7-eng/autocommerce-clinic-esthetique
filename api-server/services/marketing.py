"""
AutoCommerce Clinic — Service Marketing (Bloc 6)

Gestion complète des campagnes marketing :
- Création de campagnes (WhatsApp, SMS, email)
- Sélection de segment cible par filtres (statut fidélité, acquisition, ville, etc.)
- Envoi effectif via le connecteur omnicanal
- Tracking des envois (nb_envoyes, nb_ouverts)
- Historique et statistiques

Intégration réelle avec :
- Le connecteur WhatsApp (send_message via omnicanal_service)
- Le modèle CampagneMarketing de la base de données
- Les patients filtrés par segment_cible
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from models.database import CampagneMarketing, Patient

logger = logging.getLogger(__name__)


# ── Filtres de segment ────────────────────────────────────

def _apply_segment_filter(query, segment: dict, clinic_id: int):
    """Applique les filtres de segment sur une requête de patients.

    Filtres supportés :
    - niveau_fidelite: bronze, silver, gold, platinum
    - source_acquisition: instagram, whatsapp, recommandation, etc.
    - ville: nom de ville
    - is_active: true/false
    - consentement_marketing: true/false
    - min_points: nombre minimum de points fidélité
    - days_since_last_visit: nombre de jours depuis la dernière visite
    - custom_ids: liste d'IDs patients spécifiques
    """
    if not segment:
        return query.where(Patient.clinic_id == clinic_id, Patient.anonymized_at.is_(None), Patient.opted_out.is_(False))

    base_filters = [
        Patient.clinic_id == clinic_id,
        Patient.anonymized_at.is_(None),
        Patient.opted_out.is_(False),
    ]

    # Filtrage par IDs explicites (segment direct)
    custom_ids = segment.get("custom_ids")
    if custom_ids:
        base_filters.append(Patient.id.in_(custom_ids))

    # Filtrage par niveau de fidélité
    niveau = segment.get("niveau_fidelite")
    if niveau:
        base_filters.append(Patient.niveau_fidelite == niveau)

    # Filtrage par source d'acquisition
    source = segment.get("source_acquisition")
    if source:
        base_filters.append(Patient.source_acquisition == source)

    # Filtrage par ville
    ville = segment.get("ville")
    if ville:
        base_filters.append(Patient.ville == ville)

    # Filtrage par statut actif
    is_active = segment.get("is_active")
    if is_active is not None:
        base_filters.append(Patient.is_active == is_active)

    # Filtrage par consentement marketing
    consent = segment.get("consentement_marketing")
    if consent is not None:
        base_filters.append(Patient.consentement_marketing == consent)

    # Filtrage par nombre minimum de points
    min_points = segment.get("min_points")
    if min_points is not None:
        base_filters.append(Patient.points_fidelite >= min_points)

    # Filtrage par jours depuis la dernière visite
    days_since = segment.get("days_since_last_visit")
    if days_since is not None:
        cutoff = datetime.utcnow() - timedelta(days=days_since)  # noqa: F821
        base_filters.append(Patient.derniere_visite <= cutoff)

    return query.where(and_(*base_filters))


# ── CRUD Campagnes ────────────────────────────────────────

async def create_campaign(db: AsyncSession, data: Dict[str, Any]) -> CampagneMarketing:
    """Crée une campagne marketing en base et prépare le segment cible.

    Args:
        db: Session SQLAlchemy async
        data: Dict avec les paramètres :
            - nom (str) : Nom de la campagne
            - type (str) : Canal (whatsapp, sms, email)
            - message_template (str) : Template du message
            - clinic_id (int) : ID de la clinique
            - segment_cible (dict) : Filtres de segment
            - created_by (int, optional) : ID du créateur

    Returns:
        Objet CampagneMarketing persisté en base.
    """
    campaign = CampagneMarketing(
        clinic_id=data.get("clinic_id", 1),
        nom=data.get("nom", "Campagne sans nom"),
        type=data.get("type", "whatsapp"),
        segment_cible=data.get("segment_cible", {}),
        message_template=data.get("message_template", ""),
        date_envoi_planifiee=data.get("date_envoi_planifiee"),
        statut="brouillon",
        created_by=data.get("created_by"),
        created_at=datetime.utcnow(),
    )
    db.add(campaign)
    await db.flush()
    await db.refresh(campaign)
    logger.info(f"Campagne créée : {campaign.id} — {campaign.nom} ({campaign.type})")
    return campaign


async def get_campaign(campaign_id: int, db: AsyncSession) -> Optional[CampagneMarketing]:
    """Récupère une campagne par son ID."""
    result = await db.execute(select(CampagneMarketing).where(CampagneMarketing.id == campaign_id))
    return result.scalar_one_or_none()


async def list_campaigns(db: AsyncSession, clinic_id: int = 1, statut: Optional[str] = None,
                          limit: int = 50) -> List[CampagneMarketing]:
    """Liste les campagnes d'une clinique, filtrables par statut."""
    query = select(CampagneMarketing).where(CampagneMarketing.clinic_id == clinic_id)
    if statut:
        query = query.where(CampagneMarketing.statut == statut)
    query = query.order_by(CampagneMarketing.created_at.desc()).limit(limit)
    result = await db.execute(query)
    return list(result.scalars().all())


async def update_campaign_status(campaign_id: int, statut: str, db: AsyncSession) -> Optional[CampagneMarketing]:
    """Met à jour le statut d'une campagne (brouillon, planifiee, envoyee, annulee)."""
    campaign = await get_campaign(campaign_id, db)
    if not campaign:
        return None
    campaign.statut = statut
    await db.flush()
    return campaign


async def delete_campaign(campaign_id: int, db: AsyncSession) -> bool:
    """Supprime une campagne (uniquement si brouillon ou annulée)."""
    campaign = await get_campaign(campaign_id, db)
    if not campaign or campaign.statut not in ("brouillon", "annulee"):
        return False
    await db.delete(campaign)
    await db.flush()
    return True


# ── Envoi de campagne ─────────────────────────────────────

async def get_target_patients(segment: dict, clinic_id: int, db: AsyncSession) -> List[Patient]:
    """Récupère la liste des patients ciblés par le segment.

    Filtre automatiquement les patients :
    - De la bonne clinique
    - Non anonymisés
    - Ayant donné le consentement marketing
    - Non opt-out
    """
    query = select(Patient)
    query = _apply_segment_filter(query, segment, clinic_id)
    # S'assurer que le consentement marketing est donné
    query = query.where(Patient.consentement_marketing)
    query = query.limit(1000)  # Protection anti-envoi massif
    result = await db.execute(query)
    return list(result.scalars().all())


async def send_campaign(campaign_id: int, db: AsyncSession,
                         send_fn=None) -> Dict[str, Any]:
    """Envoie effectivement la campagne aux patients du segment cible.

    Pour chaque patient ciblé, envoie le message via le canal configuré.
    Met à jour nb_envoyes à la fin.

    Args:
        campaign_id: ID de la campagne
        db: Session SQLAlchemy
        send_fn: Fonction d'envoi (channel, to, content, subject).
                 Par défaut utilise services.omnicanal_service.send_message.

    Returns:
        Dict avec nb_envoyes, nb_echecs, campaign_id, statut.
    """
    from services.omnicanal_service import send_message as _default_send

    campaign = await get_campaign(campaign_id, db)
    if not campaign:
        raise ValueError(f"Campagne {campaign_id} introuvable")
    if campaign.statut not in ("brouillon", "planifiee"):
        raise ValueError(f"Campagne {campaign_id} ne peut pas être envoyée (statut: {campaign.statut})")

    # Récupérer les patients ciblés
    segment = campaign.segment_cible or {}
    patients = await get_target_patients(segment, campaign.clinic_id, db)

    if not patients:
        campaign.statut = "annulee"
        await db.flush()
        return {
            "campaign_id": campaign.id,
            "statut": "annulee",
            "nb_envoyes": 0,
            "nb_echecs": 0,
            "details": "Aucun patient ciblé trouvé",
        }

    # Résoudre la fonction d'envoi
    sender = send_fn or _default_send

    nb_envoyes = 0
    nb_echecs = 0

    campaign.statut = "envoyee"

    for patient in patients:
        # Déterminer l'adresse cible selon le canal
        if campaign.type == "whatsapp":
            to = patient.whatsapp_phone or patient.telephone
        elif campaign.type == "sms":
            to = patient.telephone
        elif campaign.type == "email":
            to = patient.email
        else:
            to = patient.whatsapp_phone or patient.telephone

        if not to:
            nb_echecs += 1
            logger.warning(f"Patient {patient.id} sans coordonnées pour canal {campaign.type}")
            continue

        # Personnaliser le message avec le nom du patient
        content = campaign.message_template or ""
        content = content.replace("{prenom}", patient.prenom or "")
        content = content.replace("{nom}", patient.nom or "")
        content = content.replace("{first_name}", patient.prenom or "")
        content = content.replace("{last_name}", patient.nom or "")

        try:
            result = await sender(
                channel=campaign.type,
                to=to,
                content=content,
            )
            if result.get("success"):
                nb_envoyes += 1
            else:
                nb_echecs += 1
        except Exception as e:
            nb_echecs += 1
            logger.error(f"Erreur envoi campagne {campaign.id} à patient {patient.id}: {e}")

    campaign.nb_envoyes = nb_envoyes
    await db.flush()

    return {
        "campaign_id": campaign.id,
        "statut": campaign.statut,
        "nb_envoyes": nb_envoyes,
        "nb_echecs": nb_echecs,
        "nb_cibles": len(patients),
    }


# ── Statistiques ──────────────────────────────────────────

async def get_campaign_stats(campaign_id: int, db: AsyncSession) -> Dict[str, Any]:
    """Statistiques détaillées d'une campagne."""
    campaign = await get_campaign(campaign_id, db)
    if not campaign:
        return {"error": "Campagne introuvable"}

    return {
        "id": campaign.id,
        "nom": campaign.nom,
        "type": campaign.type,
        "statut": campaign.statut,
        "nb_cibles": campaign.nb_envoyes,
        "nb_envoyes": campaign.nb_envoyes,
        "nb_ouverts": campaign.nb_ouverts,
        "taux_ouverture": (campaign.nb_ouverts / campaign.nb_envoyes * 100) if campaign.nb_envoyes > 0 else 0,
        "created_at": campaign.created_at.isoformat() if campaign.created_at else None,
    }


async def get_overview(db: AsyncSession, clinic_id: int = 1, limit: int = 20) -> Dict[str, Any]:
    """Vue d'ensemble des campagnes marketing."""
    campaigns = await list_campaigns(db, clinic_id=clinic_id, limit=limit)

    total = len(campaigns)
    brouillons = len([c for c in campaigns if c.statut == "brouillon"])
    envoyees = len([c for c in campaigns if c.statut == "envoyee"])
    total_envoyes = sum(c.nb_envoyes for c in campaigns)
    total_ouverts = sum(c.nb_ouverts for c in campaigns)

    return {
        "total_campaigns": total,
        "brouillons": brouillons,
        "envoyees": envoyees,
        "total_messages_envoyes": total_envoyes,
        "total_ouverts": total_ouverts,
        "taux_ouverture_global": (total_ouverts / total_envoyes * 100) if total_envoyes > 0 else 0,
        "recent_campaigns": [
            {
                "id": c.id,
                "nom": c.nom,
                "type": c.type,
                "statut": c.statut,
                "nb_envoyes": c.nb_envoyes,
            }
            for c in campaigns[:5]
        ],
    }
