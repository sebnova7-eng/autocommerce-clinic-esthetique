"""Services sécurité pour l'assistant WhatsApp et l'agent IA."""

from __future__ import annotations

import json
import secrets
import logging
import re
from datetime import datetime, timedelta
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from middleware.assistant_whitelist import lookup_whitelist, normalize_numero
from models.security import (
    AlerteSecurite,
    CommandeAssistant,
    ConfirmationSensible,
    NumeroWhitelist,
    SessionAssistant,
    StatutAlerteEnum,
    StatutConfirmationEnum,
    StatutSessionEnum,
    TypeAlerteEnum,
)

logger = logging.getLogger(__name__)

SESSION_TTL_MINUTES = 30
CONFIRMATION_TTL_MINUTES = 10
MAX_PAYLOAD_SIZE_KB = 32
RATE_LIMIT_PER_MINUTE = 5

# Outils d'écriture sensibles nécessitant une confirmation manuelle
SENSITIVE_WRITE_TOOLS: set[str] = {
    "send_whatsapp",
    "send_email",
    "delete_patient",
    "cancel_rdv",
    "delete_rdv",
    "update_rdv",
    "launch_campaign",
    "delete_invoice",
    "delete_facture",
    "annuler_commande",
}

def _now() -> datetime:
    return datetime.utcnow()

async def check_rate_limit(numero: str, db: AsyncSession) -> bool:
    """Vérifie le rate limit (5 req/min) par numéro."""
    # Note: Dans une version réelle, on utiliserait Redis. 
    # Ici on utilise la table CommandeAssistant comme source de vérité.
    numero_norm = await normalize_numero(numero)
    one_minute_ago = _now() - timedelta(minutes=1)
    
    res = await db.execute(
        select(CommandeAssistant)
        .where(CommandeAssistant.numero == numero_norm)
        .where(CommandeAssistant.created_at >= one_minute_ago)
    )
    count = len(res.scalars().all())
    return count < RATE_LIMIT_PER_MINUTE

def sanitize_notes(text: str) -> str:
    """Sanitisation anti-injection pour les champs de notes."""
    if not text:
        return text
    # Suppression des patterns SQL suspects
    text = re.sub(r"(?i)DROP\s+TABLE|DELETE\s+FROM|UPDATE\s+.*SET|INSERT\s+INTO", "", text)
    # Suppression des tags HTML basiques
    text = re.sub(r"<[^>]*>", "", text)
    return text.strip()

async def create_security_alert(
    db: AsyncSession,
    *,
    alert_type: str,
    description: str,
    severity: str = "moyenne",
    numero: Optional[str] = None,
    utilisateur_id: Optional[int] = None,
    details: Optional[dict[str, Any]] = None,
    clinic_id: int,
) -> AlerteSecurite:
    alerte = AlerteSecurite(
        clinic_id=clinic_id,
        type_alerte=alert_type,
        severite=severity,
        statut=StatutAlerteEnum.NOUVELLE.value,
        description=description,
        numero_concerne=await normalize_numero(numero) if numero else None,
        utilisateur_id=utilisateur_id,
        details_json=json.dumps(details, ensure_ascii=False)[:4000] if details else None,
    )
    db.add(alerte)
    await db.flush()
    return alerte

async def get_or_create_session(numero: str, current_user: dict[str, Any], db: AsyncSession) -> SessionAssistant:
    numero_norm = await normalize_numero(numero)
    res = await db.execute(
        select(SessionAssistant)
        .where(SessionAssistant.numero == numero_norm)
        .where(SessionAssistant.statut == StatutSessionEnum.ACTIVE.value)
        .order_by(SessionAssistant.created_at.desc())
    )
    session = res.scalar_one_or_none()
    now = _now()
    if session and session.expires_at > now and not session.revoked_at:
        session.derniere_activite = now
        session.nb_tours = (session.nb_tours or 0) + 1
        await db.flush()
        return session

    whitelist_row = await lookup_whitelist(numero_norm, db)
    if not whitelist_row:
        raise ValueError("Numéro whitelist introuvable")

    session = SessionAssistant(
        clinic_id=current_user["clinic_id"],
        whitelist_id=whitelist_row.id,
        utilisateur_id=current_user.get("id"),
        numero=numero_norm,
        token_session=secrets.token_urlsafe(32),
        expires_at=now + timedelta(minutes=SESSION_TTL_MINUTES),
        derniere_activite=now,
        nb_tours=1,
    )
    db.add(session)
    await db.flush()
    return session

async def rotate_whitelist_access(numero: str, revoked_by_id: int, db: AsyncSession, *, clinic_id: int) -> NumeroWhitelist:
    numero_norm = await normalize_numero(numero)
    row = await lookup_whitelist(numero_norm, db)
    if not row or row.clinic_id != clinic_id:
        raise ValueError("Numéro whitelist introuvable")
    row.last_key_rotation = _now()
    res = await db.execute(
        select(SessionAssistant)
        .where(SessionAssistant.whitelist_id == row.id)
        .where(SessionAssistant.statut == StatutSessionEnum.ACTIVE.value)
    )
    for sess in res.scalars().all():
        sess.statut = StatutSessionEnum.REVOKED.value
        sess.revoked_at = _now()
    await create_security_alert(
        db,
        alert_type=TypeAlerteEnum.TOKEN_ROTATION.value,
        description=f"Rotation d'accès WhatsApp pour {numero_norm}",
        severity="faible",
        numero=numero_norm,
        utilisateur_id=revoked_by_id,
        clinic_id=clinic_id,
    )
    await db.flush()
    return row

async def revoke_whitelist_access(numero: str, revoked_by_id: int, reason: str, db: AsyncSession, *, clinic_id: int) -> NumeroWhitelist:
    numero_norm = await normalize_numero(numero)
    res = await db.execute(select(NumeroWhitelist).where(NumeroWhitelist.numero == numero_norm, NumeroWhitelist.clinic_id == clinic_id))
    row = res.scalar_one_or_none()
    if not row:
        raise ValueError("Numéro whitelist introuvable")
    row.statut = "revoked"
    row.revoked_at = _now()
    row.revoked_by_id = revoked_by_id
    row.raison_revocation = reason[:300]
    sessions = await db.execute(
        select(SessionAssistant)
        .where(SessionAssistant.whitelist_id == row.id)
        .where(SessionAssistant.statut == StatutSessionEnum.ACTIVE.value)
    )
    for sess in sessions.scalars().all():
        sess.statut = StatutSessionEnum.REVOKED.value
        sess.revoked_at = _now()
    await db.flush()
    return row

async def log_assistant_command(
    db: AsyncSession,
    *,
    session: Optional[SessionAssistant],
    current_user: dict[str, Any],
    numero: str,
    type_commande: str,
    question: str,
    statut: str,
    reponse: Optional[str] = None,
    intent_detecte: Optional[str] = None,
    outil_appele: Optional[str] = None,
    raison_refus: Optional[str] = None,
    parametres: Optional[dict[str, Any]] = None,
    tool_payload: Optional[dict[str, Any]] = None,
    contexte: Optional[dict[str, Any]] = None,
    erreur_message: Optional[str] = None,
) -> CommandeAssistant:
    commande = CommandeAssistant(
        clinic_id=current_user["clinic_id"],
        session_id=session.id if session else None,
        whitelist_id=session.whitelist_id if session else current_user.get("whitelist_id"),
        utilisateur_id=current_user.get("id"),
        numero=await normalize_numero(numero),
        type_commande=type_commande,
        # Les contenus utilisateur/LLM ne sont pas des logs opérationnels :
        # ils sont volontairement omis pour éviter la persistance de PHI,
        # prompts, réponses ou secrets.
        question=None,
        reponse=None,
        intent_detecte=intent_detecte,
        outil_appele=outil_appele,
        role_applique=current_user.get("role"),
        statut=statut,
        raison_refus=raison_refus[:4000] if raison_refus else None,
        parametres_appel=(
            json.dumps({"keys": sorted(parametres.keys())}, ensure_ascii=False)
            if parametres else None
        ),
        tool_payload_json=None,
        contexte_json=(
            json.dumps({"keys": sorted(contexte.keys())}, ensure_ascii=False)
            if contexte else None
        ),
        erreur_message=(
            "Erreur assistant enregistrée (détail redacted)" if erreur_message else None
        ),
    )
    db.add(commande)
    await db.flush()
    return commande

async def create_confirmation(
    db: AsyncSession,
    *,
    session: SessionAssistant,
    current_user: dict[str, Any],
    numero: str,
    tool_name: str,
    tool_args: dict[str, Any],
    summary: str,
    resource_type: Optional[str] = None,
    resource_id: Optional[int] = None,
    lang: str = "fr",
) -> ConfirmationSensible:
    pending = await db.execute(
        select(ConfirmationSensible)
        .where(ConfirmationSensible.session_id == session.id)
        .where(ConfirmationSensible.statut == StatutConfirmationEnum.EN_ATTENTE.value)
        .order_by(ConfirmationSensible.created_at.desc())
    )
    for item in pending.scalars().all():
        item.statut = StatutConfirmationEnum.EXPIREE.value

    code = f"{secrets.randbelow(9000) + 1000}"
    confirmation = ConfirmationSensible(
        clinic_id=current_user["clinic_id"],
        utilisateur_id=current_user.get("id"),
        session_id=session.id,
        numero=await normalize_numero(numero),
        type_operation=tool_name,
        details_json=json.dumps({"tool_name": tool_name, "tool_args": tool_args, "summary": summary, "lang": lang}, ensure_ascii=False),
        resource_type=resource_type,
        resource_id=resource_id,
        code_confirmation=code,
        expires_at=_now() + timedelta(minutes=CONFIRMATION_TTL_MINUTES),
    )
    db.add(confirmation)
    await db.flush()
    return confirmation

async def get_pending_confirmation(session: SessionAssistant, db: AsyncSession) -> Optional[ConfirmationSensible]:
    res = await db.execute(
        select(ConfirmationSensible)
        .where(ConfirmationSensible.session_id == session.id)
        .where(ConfirmationSensible.statut == StatutConfirmationEnum.EN_ATTENTE.value)
        .order_by(ConfirmationSensible.created_at.desc())
    )
    confirmation = res.scalar_one_or_none()
    if not confirmation:
        return None
    if confirmation.expires_at <= _now():
        confirmation.statut = StatutConfirmationEnum.EXPIREE.value
        await db.flush()
        return None
    return confirmation

async def consume_confirmation_if_valid(
    message_text: str,
    *,
    session: SessionAssistant,
    current_user: dict[str, Any],
    db: AsyncSession,
) -> tuple[Optional[dict[str, Any]], Optional[str]]:
    confirmation = await get_pending_confirmation(session, db)
    if not confirmation:
        return None, None

    try:
        stored = json.loads(confirmation.details_json or "{}")
    except Exception:
        stored = {}
    lang = stored.get("lang", "fr")

    text = (message_text or "").strip().lower()
    if text in {"non", "no", "annuler", "stop", "refuser"}:
        confirmation.statut = StatutConfirmationEnum.REFUSEE.value
        await set_session_context(session, db, None)
        await db.flush()
        return None, ("الطلب تلغى." if lang == "darija" else "Action annulée.")

    expected = confirmation.code_confirmation.lower()
    normalized = text.replace("confirmer", "").replace("confirm", "").strip()
    if normalized != expected:
        msg = (f"عندك طلب تأكيد معلق. اكتب CONFIRMER {confirmation.code_confirmation} ولا NON."
               if lang == "darija" else
               f"Confirmation en attente. Répondez CONFIRMER {confirmation.code_confirmation} ou NON.")
        return None, msg

    confirmation.statut = StatutConfirmationEnum.CONFIRMEE.value
    confirmation.confirme_at = _now()
    session.derniere_activite = _now()
    await db.flush()
    return stored, None

async def get_session_context(session: SessionAssistant) -> Optional[dict[str, Any]]:
    """Récupère le contexte de session sous forme de dictionnaire."""
    if not session or not session.contexte_json:
        return None
    try:
        return json.loads(session.contexte_json)
    except json.JSONDecodeError:
        return None

async def set_session_context(session: SessionAssistant, db: AsyncSession, context: Optional[dict[str, Any]]) -> None:
    session.contexte_json = json.dumps(context, ensure_ascii=False) if context else None
    session.derniere_activite = _now()
    await db.flush()
