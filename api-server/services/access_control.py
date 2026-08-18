"""Contrôles d'appartenance communs aux services métier.

Le contexte clinique est obligatoire en production entreprise. Le seul fallback
accepté est celui d'un déploiement `internal_single_clinic` explicitement
configuré, ou des fixtures test/development pour préserver les tests locaux.
"""

from typing import Any

from config import get_settings


def user_value(user: Any, key: str, default: Any = None) -> Any:
    if isinstance(user, dict):
        return user.get(key, default)
    return getattr(user, key, default)


def clinic_id_for(user: Any = None, fallback: int | None = None) -> int:
    """Retourne le tenant courant ou échoue plutôt que d'inventer un tenant.

    En production enterprise, un contexte absent est une erreur de sécurité.
    En mono-client interne, le `CLINIC_ID` serveur est acceptable pour les
    tâches de fond qui ne disposent pas d'un utilisateur HTTP.
    """
    value = user_value(user, "clinic_id")
    try:
        clinic_id = int(value)
        if clinic_id > 0:
            return clinic_id
    except (TypeError, ValueError):
        pass

    settings = get_settings()
    if settings.env in {"test", "development"}:
        candidate = fallback if fallback is not None else settings.clinic_id or 1
        if int(candidate) > 0:
            return int(candidate)
    if settings.is_internal_single_clinic and settings.clinic_id and int(settings.clinic_id) > 0:
        return int(settings.clinic_id)
    raise PermissionError("Contexte clinique obligatoire")


def ensure_same_clinic(resource: Any, user: Any, *, not_found: str = "Ressource non trouvée") -> None:
    """Fail closed when a resource is not in the authenticated clinic."""
    try:
        clinic_id = clinic_id_for(user)
    except PermissionError as exc:
        raise PermissionError(not_found) from exc
    if resource is None or getattr(resource, "clinic_id", None) != clinic_id:
        raise PermissionError(not_found)


def ensure_patient_ownership(patient: Any, user: Any, *, allow_staff: bool = True) -> None:
    """Apply clinic isolation and the commercial ownership rule."""
    ensure_same_clinic(patient, user, not_found="Patient non trouvé")
    role = user_value(user, "role")
    if role == "commercial" and getattr(patient, "commercial_id", None) != user_value(user, "id"):
        raise PermissionError("Ce patient n'est pas rattaché à ce commercial")
    if not allow_staff and role not in {"admin", "directrice"}:
        raise PermissionError("Permission refusée")
