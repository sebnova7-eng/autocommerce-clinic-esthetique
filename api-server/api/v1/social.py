"""AutoCommerce Clinic — API Social CRM"""
from datetime import datetime
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_db
from config import get_settings
from middleware.clinic_rbac import require_role
from middleware.webhook_auth import verify_webhook_signature
from models.database import RoleEnum, AvisClient, PlateformeAvis
from services.social_crm import (
    receive_message, send_reply, list_messages,
    create_post, publier_post, enregistrer_metriques, list_posts,
    get_analytics,
)
from services.reputation import (
    get_avis,
    generer_reponse_ia,
    valider_et_publier,
)

router = APIRouter(prefix="/social", tags=["social-crm"])


class InboundMessage(BaseModel):
    plateforme: str
    contact_id: str
    contenu: str
    contact_nom: Optional[str] = None


# Correctif Bug #8 (audit) : les plateformes d'avis/distinct des
# plateformes de messagerie. Validation Pydantic normalisée en minuscules
# via l'enum ``PlateformeAvis`` côté Python (rejoint le CheckConstraint
# SQL ck_avis_plateforme_enum défini dans models/database.py).
class AvisClientIn(BaseModel):
    """Payload de création d'avis (Bug #8 : plateforme énumérée)."""
    plateforme: str
    note: Optional[int] = None
    texte: str
    auteur_nom: Optional[str] = None

    @field_validator("plateforme", mode="before")
    @classmethod
    def _normalize_plateforme(cls, v):
        # Accept "Google", "FACEBOOK", " instagram " et bascule
        # en minuscule pour correspondre aux valeurs de l'enum.
        if not isinstance(v, str):
            raise ValueError("plateforme doit être une chaîne")
        cleaned = v.strip().lower()
        allowed = {p.value for p in PlateformeAvis}
        if cleaned not in allowed:
            raise ValueError(
                f"plateforme '{v}' non supportée. Attendu : "
                f"{sorted(allowed)}"
            )
        return cleaned

    @field_validator("note")
    @classmethod
    def _validate_note(cls, v):
        if v is not None and not 1 <= v <= 5:
            raise ValueError("note doit être entre 1 et 5")
        return v


class ReplyRequest(BaseModel):
    contenu: str


class PostCreate(BaseModel):
    plateforme: str
    contenu: str
    media_url: Optional[str] = None
    date_publication_prevue: Optional[datetime] = None


class MetriquesUpdate(BaseModel):
    likes: int = 0
    commentaires: int = 0
    partages: int = 0
    impressions: int = 0


# ── Inbox ──────────────────────────────────────────────────

@router.post("/messages/webhook", status_code=status.HTTP_201_CREATED)
async def webhook_message_route(
    payload: InboundMessage,
    db: AsyncSession = Depends(get_db),
    _verified: bytes = Depends(verify_webhook_signature),
):
    """Point d'entrée pour les webhooks des plateformes (Meta/TikTok
    appelleront cette route une fois configurés côté leur dashboard).
    Signature HMAC-SHA256 obligatoire (header X-Signature) — voir
    middleware/webhook_auth.py. Chaque plateforme a son propre schéma
    de signature réel (Meta : X-Hub-Signature-256) ; à adapter lors du
    branchement effectif sans changer la logique métier ci-dessous."""
    settings = get_settings()
    clinic_id = settings.social_webhook_clinic_id
    if clinic_id is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                            detail="Mapping clinique du webhook non configuré")
    try:
        result = await receive_message(payload.plateforme, payload.contact_id, payload.contenu,
                                        db, contact_nom=payload.contact_nom, clinic_id=clinic_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return {"message_id": result["message"].id, "auto_reponse_envoyee": result["auto_reponse_envoyee"]}


@router.get("/messages")
async def list_messages_route(
    plateforme: Optional[str] = Query(None),
    statut: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role(RoleEnum.DIRECTRICE, RoleEnum.ASSISTANTE, RoleEnum.COMMERCIAL, RoleEnum.ADMIN)),
):
    clinic_id = current_user.get("clinic_id")
    if clinic_id is None:
        raise HTTPException(status_code=403, detail="Contexte clinique absent")
    messages = await list_messages(db, plateforme=plateforme, statut=statut, clinic_id=clinic_id)
    return [{"id": m.id, "plateforme": m.plateforme, "contact_id": m.contact_id,
             "contact_nom": m.contact_nom, "direction": m.direction, "contenu": m.contenu,
             "statut": m.statut, "patient_id": m.patient_id, "created_at": m.created_at} for m in messages]


@router.post("/messages/{message_id}/repondre")
async def repondre_route(
    message_id: int,
    payload: ReplyRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role(RoleEnum.DIRECTRICE, RoleEnum.ASSISTANTE, RoleEnum.COMMERCIAL, RoleEnum.ADMIN)),
):
    try:
        clinic_id = current_user.get("clinic_id")
        if clinic_id is None:
            raise HTTPException(status_code=403, detail="Contexte clinique absent")
        reponse = await send_reply(message_id, payload.contenu, db, clinic_id=clinic_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    return {"id": reponse.id, "statut": reponse.statut}


# ── Posts ──────────────────────────────────────────────────

@router.post("/posts", status_code=status.HTTP_201_CREATED)
async def create_post_route(
    payload: PostCreate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role(RoleEnum.DIRECTRICE, RoleEnum.ASSISTANTE, RoleEnum.COMMERCIAL, RoleEnum.ADMIN)),
):
    try:
        clinic_id = current_user.get("clinic_id")
        if clinic_id is None:
            raise HTTPException(status_code=403, detail="Contexte clinique absent")
        post = await create_post(payload.model_dump(), created_by=current_user["id"], db=db, clinic_id=clinic_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return {"id": post.id, "statut": post.statut}


@router.get("/posts")
async def list_posts_route(
    plateforme: Optional[str] = Query(None),
    statut: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role(RoleEnum.DIRECTRICE, RoleEnum.ASSISTANTE, RoleEnum.COMMERCIAL, RoleEnum.ADMIN)),
):
    clinic_id = current_user.get("clinic_id")
    if clinic_id is None:
        raise HTTPException(status_code=403, detail="Contexte clinique absent")
    posts = await list_posts(db, plateforme=plateforme, statut=statut, clinic_id=clinic_id)
    return [{"id": p.id, "plateforme": p.plateforme, "contenu": p.contenu, "statut": p.statut,
             "date_publication_prevue": p.date_publication_prevue, "erreur": p.erreur,
             "likes": p.likes, "commentaires": p.commentaires, "impressions": p.impressions} for p in posts]


@router.post("/posts/{post_id}/publier")
async def publier_post_route(
    post_id: int,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role(RoleEnum.DIRECTRICE, RoleEnum.ASSISTANTE, RoleEnum.COMMERCIAL, RoleEnum.ADMIN)),
):
    try:
        clinic_id = current_user.get("clinic_id")
        if clinic_id is None:
            raise HTTPException(status_code=403, detail="Contexte clinique absent")
        post = await publier_post(post_id, db, clinic_id=clinic_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return {"id": post.id, "statut": post.statut, "erreur": post.erreur}


@router.patch("/posts/{post_id}/metriques")
async def metriques_route(
    post_id: int,
    payload: MetriquesUpdate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role(RoleEnum.DIRECTRICE, RoleEnum.ASSISTANTE, RoleEnum.ADMIN)),
):
    try:
        clinic_id = current_user.get("clinic_id")
        if clinic_id is None:
            raise HTTPException(status_code=403, detail="Contexte clinique absent")
        post = await enregistrer_metriques(post_id, payload.likes, payload.commentaires,
                                            payload.partages, payload.impressions, db, clinic_id=clinic_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    return {"id": post.id, "likes": post.likes, "commentaires": post.commentaires,
            "impressions": post.impressions}


@router.get("/analytics")
async def analytics_route(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role(RoleEnum.DIRECTRICE, RoleEnum.ASSISTANTE, RoleEnum.COMMERCIAL, RoleEnum.ADMIN)),
):
    clinic_id = current_user.get("clinic_id")
    if clinic_id is None:
        raise HTTPException(status_code=403, detail="Contexte clinique absent")
    return await get_analytics(db, clinic_id=clinic_id)


# ── Avis Clients / E-Réputation ───────────────────────────

@router.get("/avis", response_model=List[dict])
async def list_avis(
    plateforme: Optional[str] = Query(
        None,
        description="Filtre plateforme (`google` | `instagram` | `facebook`). "
        "Correctif Bug #8 : valeurs normalisées en minuscules via PlateformeAvis.",
    ),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role(RoleEnum.DIRECTRICE, RoleEnum.ASSISTANTE, RoleEnum.ADMIN)),
):
    """Liste les avis clients récoltés."""
    # Correctif Bug #8 (audit) : on valide/normalise le query param
    # en utilisant le même enum que les inserts pour éviter qu'un client
    # envoie ``?plateforme=FACEBOOK`` et obtienne une liste vide (le
    # filtre SQL cherchait alors ``plateforme == 'FACEBOOK'`` alors que
    # les lignes sont stockées en minuscules).
    if plateforme is not None:
        cleaned = plateforme.strip().lower()
        allowed = {p.value for p in PlateformeAvis}
        if cleaned not in allowed:
            raise HTTPException(
                status_code=400,
                detail=f"plateforme '{plateforme}' non supportée. "
                       f"Attendu : {sorted(allowed)}",
            )
        plateforme = cleaned
    avis_list = await get_avis(
        db, plateforme, clinic_id=current_user["clinic_id"],
    )
    return [
        {
            "id": a.id,
            "plateforme": a.plateforme,
            "note": a.note,
            "texte": a.texte,
            "auteur_nom": a.auteur_nom,
            "reponse_suggeree_ia": a.reponse_suggeree_ia,
            "reponse_publiee": a.reponse_publiee,
            "statut": a.statut,
            "created_at": a.created_at.isoformat(),
        }
        for a in avis_list
    ]


@router.post("/avis/{avis_id}/suggerer-reponse", response_model=dict)
async def suggest_ia_reply(
    avis_id: int,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role(RoleEnum.DIRECTRICE, RoleEnum.ASSISTANTE, RoleEnum.ADMIN)),
):
    """Génère une suggestion de réponse par IA."""
    from sqlalchemy import select
    result = await db.execute(select(AvisClient).where(
        AvisClient.id == avis_id,
        AvisClient.clinic_id == current_user["clinic_id"],
    ))
    avis = result.scalar_one_or_none()
    if not avis:
        raise HTTPException(status_code=404, detail="Avis non trouvé")
    
    reponse = await generer_reponse_ia(
        avis, db,
        budget_subject=f"clinic:{current_user['clinic_id']}:user:{current_user['id']}",
    )
    return {"reponse_suggeree": reponse}


class ValidationRequest(BaseModel):
    reponse_finale: str


@router.post("/avis/{avis_id}/valider", response_model=dict)
async def validate_avis_reply(
    avis_id: int,
    data: ValidationRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role(RoleEnum.DIRECTRICE, RoleEnum.ASSISTANTE, RoleEnum.ADMIN)),
):
    """Valide et publie la réponse à un avis."""
    try:
        avis = await valider_et_publier(
            avis_id, data.reponse_finale, db,
            clinic_id=current_user["clinic_id"],
        )
        return {"status": "success", "avis_id": avis.id, "statut": avis.statut}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# Note Bug #7 (audit) :
#   L'endpoint ``POST /social/avis/ingestion-google-test`` (ADMIN-only)
#   injectait en base un faux avis "Jean Dupont, 5★, Superbe expérience…"
#   à chaque appel. Même restreint au rôle ADMIN, un admin distrait pouvait
#   polluer la table ``avis_clients`` avec des avis fictifs qui
#   apparaissaient dans le dashboard e-réputation. En production, ce flux
#   sera déclenché par un cron ou un webhook Google My Business.
#
#   Correctif appliqué :
#   - Endpoint supprimé des routes actives (plus aucune exposition HTTP).
#   - Logique de simulation migrée dans ``scripts/ingest_google_review.py``
#     (CLI, exécutable en local pour smoke-tests et démos, jamais servie
#     par FastAPI). Ce script accepte des paramètres (plateforme, note,
#     texte, auteur) et n'écrit rien sans confirmation interactive.
#   - En production, remplacer ce script par un vrai connecteur Google
#     My Business API (oauth2 + refresh token, conforme Meta/TikTok).
