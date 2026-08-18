"""
AutoCommerce Clinic — API Messagerie interne d'équipe.
Endpoints : POST /messages, GET /messages, GET /messages/{id},
            PUT /messages/{id}/lu, DELETE /messages/{id},
            GET /messages/sent, GET /messages/unread-count
"""
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_db
from middleware.clinic_rbac import require_role
from models.database import RoleEnum
from services.notification_equipe import (
    envoyer_message,
    lister_messages_reception,
    lister_messages_envoyes,
    get_message,
    marquer_lu,
    supprimer_message,
    compter_non_lus,
)

router = APIRouter(prefix="/equipe", tags=["equipe"])

ROLES_EQUIPE = (
    RoleEnum.DIRECTRICE,
    RoleEnum.ADMIN,
    RoleEnum.MEDECIN,
    RoleEnum.ESTHETICIENNE,
    RoleEnum.ASSISTANTE,
    RoleEnum.COMMERCIAL,
)


class MessageCreate(BaseModel):
    """Payload pour envoyer un message."""
    destinataire_id: int
    sujet: str
    contenu: str


class MessageRead(BaseModel):
    """Réponse sérialisée d'un message."""
    id: int
    clinic_id: int
    expediteur_id: int
    destinataire_id: int
    expediteur_nom: str
    expediteur_prenom: str
    destinataire_nom: str
    destinataire_prenom: str
    sujet: str
    contenu: str
    lu: bool
    lu_a: Optional[datetime]
    cree_a: datetime

    class Config:
        from_attributes = True


def _serialize_message(msg, exp_nom="", exp_prenom="", dest_nom="", dest_prenom="") -> dict:
    return {
        "id": msg.id,
        "clinic_id": msg.clinic_id,
        "expediteur_id": msg.expediteur_id,
        "destinataire_id": msg.destinataire_id,
        "expediteur_nom": exp_nom,
        "expediteur_prenom": exp_prenom,
        "destinataire_nom": dest_nom,
        "destinataire_prenom": dest_prenom,
        "sujet": msg.sujet,
        "contenu": msg.contenu,
        "lu": msg.lu,
        "lu_a": msg.lu_a,
        "cree_a": msg.cree_a,
    }


# ── Envoyer un message ─────────────────────────────────────

@router.post("/messages", status_code=status.HTTP_201_CREATED)
async def envoyer_message_route(
    payload: MessageCreate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role(*ROLES_EQUIPE)),
):
    """Envoyer un message interne à un membre de l'équipe."""
    try:
        msg = await envoyer_message(
            db=db,
            expediteur_id=current_user["id"],
            destinataire_id=payload.destinataire_id,
            sujet=payload.sujet,
            contenu=payload.contenu,
            clinic_id=current_user["clinic_id"],
        )
        # On recharge pour avoir les noms des utilisateurs
        from models.database import Utilisateur
        from sqlalchemy import select
        exp_result = await db.execute(select(Utilisateur).where(Utilisateur.id == msg.expediteur_id))
        exp = exp_result.scalar_one_or_none()
        dest_result = await db.execute(select(Utilisateur).where(Utilisateur.id == msg.destinataire_id))
        dest = dest_result.scalar_one_or_none()
        return _serialize_message(msg, exp.nom if exp else "", exp.prenom if exp else "",
                                  dest.nom if dest else "", dest.prenom if dest else "")
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# ── Boîte de réception ─────────────────────────────────────

@router.get("/messages")
async def lister_messages_route(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role(*ROLES_EQUIPE)),
):
    """Lister les messages reçus (boîte de réception)."""
    offset = (page - 1) * page_size
    messages = await lister_messages_reception(
        db=db,
        utilisateur_id=current_user["id"],
        clinic_id=current_user["clinic_id"],
        limit=page_size,
        offset=offset,
    )
    # Charger les noms
    from models.database import Utilisateur
    from sqlalchemy import select
    result = []
    for msg in messages:
        exp_result = await db.execute(select(Utilisateur).where(Utilisateur.id == msg.expediteur_id))
        exp = exp_result.scalar_one_or_none()
        dest_result = await db.execute(select(Utilisateur).where(Utilisateur.id == msg.destinataire_id))
        dest = dest_result.scalar_one_or_none()
        result.append(_serialize_message(
            msg,
            exp.nom if exp else "", exp.prenom if exp else "",
            dest.nom if dest else "", dest.prenom if dest else "",
        ))
    return result


# ── Messages envoyés ───────────────────────────────────────

@router.get("/messages/sent")
async def lister_sent_route(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role(*ROLES_EQUIPE)),
):
    """Lister les messages envoyés."""
    offset = (page - 1) * page_size
    messages = await lister_messages_envoyes(
        db=db,
        utilisateur_id=current_user["id"],
        clinic_id=current_user["clinic_id"],
        limit=page_size,
        offset=offset,
    )
    from models.database import Utilisateur
    from sqlalchemy import select
    result = []
    for msg in messages:
        exp_result = await db.execute(select(Utilisateur).where(Utilisateur.id == msg.expediteur_id))
        exp = exp_result.scalar_one_or_none()
        dest_result = await db.execute(select(Utilisateur).where(Utilisateur.id == msg.destinataire_id))
        dest = dest_result.scalar_one_or_none()
        result.append(_serialize_message(
            msg,
            exp.nom if exp else "", exp.prenom if exp else "",
            dest.nom if dest else "", dest.prenom if dest else "",
        ))
    return result


# ── Compter non-lus ────────────────────────────────────────

@router.get("/messages/unread-count")
async def unread_count_route(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role(*ROLES_EQUIPE)),
):
    """Nombre de messages non lus."""
    count = await compter_non_lus(
        db=db,
        utilisateur_id=current_user["id"],
        clinic_id=current_user["clinic_id"],
    )
    return {"unread_count": count}


# ── Détail d'un message ────────────────────────────────────

@router.get("/messages/{message_id}")
async def get_message_route(
    message_id: int,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role(*ROLES_EQUIPE)),
):
    """Récupérer un message spécifique."""
    msg = await get_message(
        db=db,
        message_id=message_id,
        utilisateur_id=current_user["id"],
        clinic_id=current_user["clinic_id"],
    )
    if not msg:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message introuvable")

    from models.database import Utilisateur
    from sqlalchemy import select
    exp_result = await db.execute(select(Utilisateur).where(Utilisateur.id == msg.expediteur_id))
    exp = exp_result.scalar_one_or_none()
    dest_result = await db.execute(select(Utilisateur).where(Utilisateur.id == msg.destinataire_id))
    dest = dest_result.scalar_one_or_none()
    return _serialize_message(
        msg,
        exp.nom if exp else "", exp.prenom if exp else "",
        dest.nom if dest else "", dest.prenom if dest else "",
    )


# ── Marquer comme lu ───────────────────────────────────────

@router.put("/messages/{message_id}/lu")
async def marquer_lu_route(
    message_id: int,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role(*ROLES_EQUIPE)),
):
    """Marquer un message comme lu (destinataire uniquement)."""
    try:
        msg = await marquer_lu(
            db=db,
            message_id=message_id,
            utilisateur_id=current_user["id"],
            clinic_id=current_user["clinic_id"],
        )
        return {"id": msg.id, "lu": msg.lu, "lu_a": msg.lu_a}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


# ── Supprimer un message ───────────────────────────────────

@router.delete("/messages/{message_id}")
async def supprimer_message_route(
    message_id: int,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role(*ROLES_EQUIPE)),
):
    """Supprimer un message (destinataire ou expéditeur)."""
    try:
        await supprimer_message(
            db=db,
            message_id=message_id,
            utilisateur_id=current_user["id"],
            clinic_id=current_user["clinic_id"],
        )
        return {"detail": "Message supprimé"}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
