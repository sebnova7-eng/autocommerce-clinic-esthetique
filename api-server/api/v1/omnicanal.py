"""
AutoCommerce Clinic — API Omnicanal (WhatsApp, Email, SMS, TikTok, IG, FB)

Routes pour le CRM omnicanal :
  - Conversations : CRUD, assignation, tags, fermeture
  - Messages : envoi, réception, retry, accusés de réception
  - Canaux : statut, configuration
  - Webhooks : entrée multi-canal
"""

from datetime import datetime
import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_db, limiter
from middleware.auth import get_current_active_user
from middleware.clinic_rbac import check_permission
from services.omnicanal_service import (
    list_conversations,
    get_conversation_messages,
    close_conversation,
    send_reply,
    get_channel_stats,
)
from services.omnicanal.factory import OmnicanalFactory
from config import get_settings

router = APIRouter(prefix="/omnicanal", tags=["omnicanal"])
logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════
# SCHÉMAS
# ═══════════════════════════════════════════════════════════

class ConversationOut(BaseModel):
    id: int
    canal: str
    contact_external_id: str
    contact_nom: Optional[str] = None
    patient_id: Optional[int] = None
    statut: str
    nb_messages: int
    tags: Optional[str] = None
    assignee_id: Optional[int] = None
    dernier_message_at: Optional[datetime] = None
    created_at: datetime


class MessageOut(BaseModel):
    id: int
    conversation_id: int
    direction: str
    type_message: str
    contenu: Optional[str] = None
    statut: str
    external_message_id: Optional[str] = None
    delivre_a: Optional[datetime] = None
    lu_a: Optional[datetime] = None
    nb_retries: int
    reponse_auto: bool
    patient_id: Optional[int] = None
    envoye_par_id: Optional[int] = None
    created_at: datetime


class SendMessageRequest(BaseModel):
    conversation_id: int
    contenu: str
    type_message: str = "texte"
    media_url: Optional[str] = None
    template_name: Optional[str] = None
    template_params: Optional[dict] = None


class ChannelHealthOut(BaseModel):
    channel: str
    enabled: bool
    configured: bool
    status: str
    last_error_at: Optional[datetime] = None


class AddTagsRequest(BaseModel):
    tags: List[str]


class AssignRequest(BaseModel):
    assignee_id: int


# ═══════════════════════════════════════════════════════════
# SANTÉ & CANAUX
# ═══════════════════════════════════════════════════════════

@router.get("/health", response_model=List[ChannelHealthOut])
async def get_omnicanal_health(
    current_user: dict = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Expose la santé réelle de chaque canal."""
    if not check_permission(current_user.get("role", ""), "marketing", "read"):
        raise HTTPException(status_code=403, detail="Accès refusé")
        
    factory = OmnicanalFactory()
    settings = get_settings()
    results = []
    
    for channel_name in factory.get_all_connectors():
        try:
            connector = factory.get_connector(channel_name)
            status_info = await connector.get_channel_status()
            
            enabled = True
            if channel_name == "tiktok":
                enabled = settings.tiktok_enabled
            elif channel_name == "instagram":
                enabled = settings.instagram_enabled
            elif channel_name == "facebook":
                enabled = settings.facebook_enabled
            
            results.append({
                "channel": channel_name,
                "enabled": enabled,
                "configured": status_info.get("configured", False),
                "status": status_info.get("status", "unknown"),
                "last_error_at": None
            })
        except Exception as e:
            logger.error(f"Health check failed for {channel_name}: {e}")
            results.append({
                "channel": channel_name,
                "enabled": False,
                "configured": False,
                "status": "error",
                "last_error_at": datetime.now()
            })
            
    return results


# ═══════════════════════════════════════════════════════════
# CONVERSATIONS
# ═══════════════════════════════════════════════════════════

@router.get("/conversations", response_model=List[ConversationOut])
@limiter.limit("60/minute")
async def api_list_conversations(
    request: Request,
    canal: Optional[str] = Query(None),
    statut: Optional[str] = Query(None),
    patient_id: Optional[int] = Query(None),
    limit: int = Query(50, le=200),
    offset: int = Query(0),
    current_user: dict = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Liste les conversations avec filtres."""
    if not check_permission(current_user.get("role", ""), "marketing", "read"):
        raise HTTPException(status_code=403, detail="Accès refusé")
    conversations = await list_conversations(
        db=db, canal=canal, statut=statut, patient_id=patient_id,
        clinic_id=current_user["clinic_id"], limit=limit, offset=offset,
    )
    return conversations


@router.get("/conversations/{conversation_id}/messages", response_model=List[MessageOut])
async def api_get_conversation_messages(
    conversation_id: int,
    request: Request,
    limit: int = Query(200, le=500),
    offset: int = Query(0),
    current_user: dict = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Messages d'une conversation (thread)."""
    if not check_permission(current_user.get("role", ""), "marketing", "read"):
        raise HTTPException(status_code=403, detail="Accès refusé")
    messages = await get_conversation_messages(
        conversation_id, db, limit, offset, clinic_id=current_user["clinic_id"]
    )
    return messages


@router.post("/conversations/{conversation_id}/close")
async def api_close_conversation(
    conversation_id: int,
    request: Request,
    current_user: dict = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Ferme une conversation."""
    if not check_permission(current_user.get("role", ""), "marketing", "write"):
        raise HTTPException(status_code=403, detail="Accès refusé")
    conv = await close_conversation(
        conversation_id, db, clinic_id=current_user["clinic_id"]
    )
    return {"message": "Conversation fermée", "conversation": conv}


# ═══════════════════════════════════════════════════════════
# MESSAGES
# ═══════════════════════════════════════════════════════════

@router.post("/messages/send", response_model=dict)
async def api_send_message(
    payload: SendMessageRequest,
    request: Request,
    current_user: dict = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Envoie un message de réponse dans une conversation."""
    if not check_permission(current_user.get("role", ""), "marketing", "write"):
        raise HTTPException(status_code=403, detail="Accès refusé")
    
    # Vérification du canal pour 503 gating
    from models.omnicanal import Conversation
    from sqlalchemy import select
    q = select(Conversation).where(
        Conversation.id == payload.conversation_id,
        Conversation.clinic_id == current_user["clinic_id"],
    )
    res = await db.execute(q)
    conv = res.scalar_one_or_none()
    
    if conv:
        settings = get_settings()
        disabled = False
        if conv.canal == "tiktok" and not settings.tiktok_enabled:
            disabled = True
        elif conv.canal == "instagram" and not settings.instagram_enabled:
            disabled = True
        elif conv.canal == "facebook" and not settings.facebook_enabled:
            disabled = True
        
        if disabled:
            raise HTTPException(
                status_code=503,
                detail={"error": "channel_disabled", "message": f"Le canal {conv.canal} est désactivé."}
            )

    result = await send_reply(
        conversation_id=payload.conversation_id,
        content=payload.contenu,
        db=db,
        type_message=payload.type_message,
        media_url=payload.media_url,
        template_name=payload.template_name,
        template_params=payload.template_params,
        envoye_par_id=current_user.get("id"),
        clinic_id=current_user["clinic_id"],
    )
    return {"success": True, "message": result}


# ═══════════════════════════════════════════════════════════
# WEBHOOKS
# ═══════════════════════════════════════════════════════════

@router.post("/webhook/{canal}")
async def api_webhook(
    canal: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Reçoit un webhook entrant. Retourne 202 si accepté, 401/503 sur erreur signature/config."""
    from middleware.webhook_omnicanal import process_incoming_webhook
    
    result = await process_incoming_webhook(request, db, path_canal=canal)
    
    if result.get("error"):
        # Mapping erreur vers code HTTP
        err = result["error"].lower()
        if "signature" in err:
            return Response(content=result["error"], status_code=401)
        if any(kw in err for kw in ("secret", "disabled", "configuré", "non configure")):
            return Response(content=result["error"], status_code=503)
        return Response(content=result["error"], status_code=400)

    return Response(status_code=202)


@router.get("/channels")
async def api_channel_status(
    current_user: dict = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Statut des canaux (version simplifiée)."""
    if not check_permission(current_user.get("role", ""), "marketing", "read"):
        raise HTTPException(status_code=403, detail="Accès refusé")
    return await get_channel_stats(db)
