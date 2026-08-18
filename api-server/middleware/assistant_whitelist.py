"""
AutoCommerce Clinic — Middleware whitelist assistant (Bloc 2)

Vérifie, **pour chaque message WhatsApp entrant**, que :

  1. Le numéro est dans `numeros_whitelist` avec statut ACTIVE et non expiré.
  2. Le numéro est rattaché à un utilisateur existant de la clinique
     (`utilisateur_id` FK), avec `is_active = True`.

Cette source d'identité est **strictement** :
  - la whitelist en base (jamais déduite du contenu du message),
  - l'utilisateur interne lié (rôle RBAC = source de vérité pour
    la matrice `middleware.clinic_rbac.py`).

Aucune logique écrite en dur dans le code — la whitelist est
modifiable par l'admin via les routes `/api/v1/assistant/whitelist`.
"""

from datetime import datetime
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.database import Utilisateur
from models.security import NumeroWhitelist, StatutWhitelistEnum


class WhitelistRejection(HTTPException):
    def __init__(self, reason: str):
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Numéro non autorisé : {reason}",
        )


async def _normalize(numero: str) -> str:
    """Normalisation minimale : on retire espaces, tirets, parenthèses.
    On NE déduit RIEN du contenu — uniquement du format du numéro.
    """
    return "".join(c for c in numero if c.isdigit() or c == "+")


async def normalize_numero(numero: str) -> str:
    return await _normalize(numero)


async def lookup_whitelist(
    numero: str, db: AsyncSession
) -> Optional[NumeroWhitelist]:
    """Cherche un numéro actif non expiré dans la whitelist."""
    numero_norm = await _normalize(numero)
    res = await db.execute(
        select(NumeroWhitelist).where(NumeroWhitelist.numero == numero_norm)
    )
    row = res.scalar_one_or_none()
    if not row:
        return None
    if row.statut != StatutWhitelistEnum.ACTIVE.value:
        return None
    if row.expires_at and row.expires_at < datetime.utcnow():
        return None
    return row


async def resolve_user_from_whitelist(
    numero: str, db: AsyncSession
) -> tuple[NumeroWhitelist, Utilisateur]:
    """Vérifie whitelist + utilisateur lié. Renvoie (whitelist_row, user).

    Lève WhitelistRejection si l'une des conditions n'est pas remplie.
    """
    row = await lookup_whitelist(numero, db)
    if not row:
        await _record_rejection(numero, db)
        raise WhitelistRejection("numéro absent, révoqué ou expiré")

    if not row.utilisateur_id:
        raise WhitelistRejection("numéro whitelisté sans utilisateur lié")

    res = await db.execute(
        select(Utilisateur).where(Utilisateur.id == row.utilisateur_id)
    )
    user = res.scalar_one_or_none()
    if not user or not user.is_active:
        raise WhitelistRejection("utilisateur lié inactif")

    return row, user


async def _record_rejection(numero: str, db: AsyncSession, clinic_id: Optional[int] = None) -> None:
    """Crée une alerte de sécurité (Bloc 3 anticipé). Best-effort."""
    if not isinstance(clinic_id, int) or clinic_id <= 0:
        return
    try:
        from models.security import AlerteSecurite, TypeAlerteEnum, StatutAlerteEnum
        alerte = AlerteSecurite(
            clinic_id=clinic_id,
            type_alerte=TypeAlerteEnum.NUMERO_NON_AUTORISE.value,
            severite="moyenne",
            statut=StatutAlerteEnum.NOUVELLE.value,
            description=f"Tentative d'accès assistant depuis le numéro {numero}",
            numero_concerne=await _normalize(numero),
            details_json=None,
        )
        db.add(alerte)
        await db.flush()
    except Exception:
        # Ne jamais faire échouer le flux principal pour une alerte best-effort
        pass


async def ensure_can_receive_assistant_message(
    numero: str, db: AsyncSession
) -> dict:
    """API pratique pour l'orchestrateur webhooks : renvoie un
    current_user-like dict si OK, lève HTTPException sinon.
    """
    row, user = await resolve_user_from_whitelist(numero, db)
    return {
        "id": user.id,
        "role": user.role,
        "nom": user.nom,
        "prenom": user.prenom,
        "email": user.email,
        "whitelist_id": row.id,
        "clinic_id": user.clinic_id,
    }
