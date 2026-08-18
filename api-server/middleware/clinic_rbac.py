"""
AutoCommerce Clinic — Matrice RBAC stricte

DIRECTRICE   : tout sauf contenu chiffré médical (lecture seule)
MEDECIN      : dossier complet + photos + notes
ESTHETICIENNE: actes esthétiques (PAS antécédents)
ASSISTANTE   : agenda + facturation (PAS dossiers)
COMMERCIAL   : ses patientes uniquement, contact info seulement
ADMIN        : tout (technique)
PATIENT(OTP) : ses données uniquement (lecture)
"""

from typing import Any, Iterable

from fastapi import Depends, HTTPException, status

from middleware.auth import get_current_active_user
from models.database import RoleEnum, Utilisateur


# ── Matrice des permissions ────────────────────────────────

RESOURCE_PERMISSIONS = {
    "patients": {
        RoleEnum.DIRECTRICE: ["read", "write", "delete"],
        RoleEnum.MEDECIN: ["read", "write"],
        RoleEnum.ESTHETICIENNE: ["read", "write"],
        RoleEnum.ASSISTANTE: ["read", "write"],
        RoleEnum.COMMERCIAL: ["read"],  # Ses patientes uniquement
        RoleEnum.ADMIN: ["read", "write", "delete"],
    },
    "dossiers_medicaux": {
        RoleEnum.DIRECTRICE: ["read"],  # Lecture seule administrative, PAS de contenu médical déchiffré
        RoleEnum.MEDECIN: ["read", "write"],
        RoleEnum.ESTHETICIENNE: ["read", "write"],  # PAS antécédents
        RoleEnum.ASSISTANTE: [],  # PAS accès
        RoleEnum.COMMERCIAL: [],  # PAS accès
        RoleEnum.ADMIN: ["read", "write", "delete"],
    },
    "photos": {
        RoleEnum.DIRECTRICE: [],  # PAS accès photos médicales (données de santé sensibles)
        RoleEnum.MEDECIN: ["read", "write", "delete"],
        RoleEnum.ESTHETICIENNE: ["read", "write"],
        RoleEnum.ASSISTANTE: [],  # PAS accès photos médicales
        RoleEnum.COMMERCIAL: [],  # PAS accès
        RoleEnum.ADMIN: ["read", "write", "delete"],
    },
    "agenda": {
        RoleEnum.DIRECTRICE: ["read", "write", "delete"],
        RoleEnum.MEDECIN: ["read", "write"],
        RoleEnum.ESTHETICIENNE: ["read", "write"],
        RoleEnum.ASSISTANTE: ["read", "write", "delete"],
        RoleEnum.COMMERCIAL: ["read"],
        RoleEnum.ADMIN: ["read", "write", "delete"],
    },
    "factures": {
        RoleEnum.DIRECTRICE: ["read", "write", "delete"],
        RoleEnum.MEDECIN: ["read"],
        RoleEnum.ESTHETICIENNE: ["read"],
        RoleEnum.ASSISTANTE: ["read", "write"],
        RoleEnum.COMMERCIAL: ["read"],  # Ses patientes
        RoleEnum.ADMIN: ["read", "write", "delete"],
    },
    "commissions": {
        RoleEnum.DIRECTRICE: ["read", "write", "validate"],
        RoleEnum.MEDECIN: [],
        RoleEnum.ESTHETICIENNE: [],
        RoleEnum.ASSISTANTE: [],
        RoleEnum.COMMERCIAL: ["read"],  # Ses commissions
        RoleEnum.ADMIN: ["read", "write", "delete"],
    },
    "stock_injectables": {
        RoleEnum.DIRECTRICE: ["read", "write", "delete"],
        RoleEnum.MEDECIN: ["read", "write"],
        RoleEnum.ESTHETICIENNE: ["read", "write"],
        RoleEnum.ASSISTANTE: ["read", "write"],
        RoleEnum.COMMERCIAL: [],
        RoleEnum.ADMIN: ["read", "write", "delete"],
    },
    "depenses": {
        RoleEnum.DIRECTRICE: ["read", "write", "delete", "validate"],
        RoleEnum.MEDECIN: [],
        RoleEnum.ESTHETICIENNE: [],
        RoleEnum.ASSISTANTE: ["read", "write"],
        RoleEnum.COMMERCIAL: [],
        RoleEnum.ADMIN: ["read", "write", "delete"],
    },
    "recrutement": {
        RoleEnum.DIRECTRICE: ["read", "write", "delete"],
        RoleEnum.MEDECIN: ["read"],
        RoleEnum.ESTHETICIENNE: [],
        RoleEnum.ASSISTANTE: ["read", "write"],
        RoleEnum.COMMERCIAL: [],
        RoleEnum.ADMIN: ["read", "write", "delete"],
    },
    "marketing": {
        RoleEnum.DIRECTRICE: ["read", "write", "delete"],
        RoleEnum.MEDECIN: [],
        RoleEnum.ESTHETICIENNE: [],
        RoleEnum.ASSISTANTE: ["read", "write"],
        RoleEnum.COMMERCIAL: ["read", "write"],
        RoleEnum.ADMIN: ["read", "write", "delete"],
    },
    "settings": {
        RoleEnum.DIRECTRICE: ["read", "write"],
        RoleEnum.ADMIN: ["read", "write", "delete"],
    },
}


def _extract_user_role(current_user: Any) -> str | None:
    """Accepte le contrat principal de l'app (dict) ET les objets ORM/mock des tests."""
    if isinstance(current_user, dict):
        return current_user.get("role")
    return getattr(current_user, "role", None)


def _normalize_allowed_roles(allowed_roles: tuple[Any, ...]) -> list[RoleEnum]:
    """Accepte require_role(RoleEnum.A, RoleEnum.B) ET
    require_role([RoleEnum.A, RoleEnum.B])."""
    normalized: list[RoleEnum] = []

    for role in allowed_roles:
        if isinstance(role, RoleEnum):
            normalized.append(role)
            continue

        if isinstance(role, Iterable) and not isinstance(role, (str, bytes)):
            for item in role:
                if not isinstance(item, RoleEnum):
                    raise TypeError(f"Rôle invalide: {item!r}")
                normalized.append(item)
            continue

        raise TypeError(f"Rôle invalide: {role!r}")

    return normalized


def require_role(*allowed_roles: RoleEnum):
    """Décorateur FastAPI Depends vérifiant le rôle de l'utilisateur.

    Usage:
        @router.get("/patients")
        async def list_patients(
            current_user=Depends(require_role(RoleEnum.MEDECIN, RoleEnum.DIRECTRICE)),
        ):
            ...
    """
    normalized_roles = _normalize_allowed_roles(allowed_roles)
    allowed_values = [r.value for r in normalized_roles]

    async def role_checker(current_user: dict | Utilisateur = Depends(get_current_active_user)) -> dict | Utilisateur:
        user_role = _extract_user_role(current_user)

        if not user_role:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Rôle utilisateur non défini",
            )

        if user_role not in allowed_values:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Accès refusé. Rôles autorisés : {allowed_values}",
            )

        return current_user

    return role_checker


def check_permission(user_role: str, resource: str, action: str) -> bool:
    """Vérifie si un rôle a la permission sur une ressource.

    Args:
        user_role: Valeur du rôle (ex: "medecin")
        resource: Nom de la ressource (ex: "dossiers_medicaux")
        action: Action demandée (ex: "read", "write")

    Returns:
        True si autorisé, False sinon
    """
    if resource not in RESOURCE_PERMISSIONS:
        return False

    role_enum = None
    for r in RoleEnum:
        if r.value == user_role:
            role_enum = r
            break

    if not role_enum:
        return False

    permissions = RESOURCE_PERMISSIONS[resource].get(role_enum, [])
    return action in permissions


class PermissionDenied(HTTPException):
    def __init__(self, detail: str = "Permission refusée"):
        super().__init__(status_code=status.HTTP_403_FORBIDDEN, detail=detail)
