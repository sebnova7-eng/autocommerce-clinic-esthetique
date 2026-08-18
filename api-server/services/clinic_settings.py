from __future__ import annotations

"""
AutoCommerce Clinic — Gestion des paramètres clinique
Cache Redis 5min, lecture/écriture sans redéploiement
"""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import get_settings
from models.database import ClinicSetting


CACHE_TTL_SECONDS = 300
_SETTING_CACHE: dict[tuple[int, str], tuple[Any, datetime]] = {}


def _resolve_clinic_id(clinic_id: Optional[int]) -> int:
    if clinic_id is not None:
        if clinic_id <= 0:
            raise ValueError("clinic_id doit être un entier positif")
        return clinic_id
    if get_settings().env in {"test", "development"}:
        return 1
    raise RuntimeError("clinic_id explicite obligatoire hors environnement de test/développement")

JsonScalar = str | int | float | bool | None
JsonValue = JsonScalar | list["JsonValue"] | dict[str, "JsonValue"]


def _assert_json_compatible(value: Any, path: str = "value") -> None:
    """Valide récursivement une structure JSON sans déclencher les
    régressions de récursion Pydantic observées à l'import.
    
    On accepte uniquement :
    - scalaires JSON (str, int, float, bool, None)
    - listes récursives
    - dictionnaires à clés str et valeurs récursivement JSON.
    """
    if isinstance(value, (str, int, float, bool)) or value is None:
        return

    if isinstance(value, list):
        for index, item in enumerate(value):
            _assert_json_compatible(item, f"{path}[{index}]")
        return

    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                raise ValueError(f"{path}: JSON object keys must be strings")
            _assert_json_compatible(item, f"{path}.{key}")
        return

    raise ValueError(f"{path}: unsupported JSON value type {type(value).__name__}")


class _SettingPayloadModel(BaseModel):
    payload: dict[str, Any]

    @field_validator("payload")
    @classmethod
    def validate_payload(cls, value: dict[str, Any]) -> dict[str, Any]:
        _assert_json_compatible(value)
        return value


def _normalize_setting_value(value: Any) -> dict[str, JsonValue]:
    """Valide strictement la payload des paramètres avant écriture DB."""
    payload = value if isinstance(value, dict) else {"value": value}
    validated = _SettingPayloadModel.model_validate({"payload": payload}, strict=True)
    return validated.payload


async def get_setting(
    key: str,
    db: AsyncSession,
    default: Any = None,
    clinic_id: Optional[int] = None,
) -> Any:
    """Lit un paramètre clinique avec cache LRU en mémoire.

    Args:
        key: Clé du paramètre (ex: "clinic.name")
        db: Session async SQLAlchemy
        default: Valeur par défaut si non trouvé

    Returns:
        Valeur du paramètre (déjà parsée depuis JSON) ou default
    """
    resolved_clinic_id = _resolve_clinic_id(clinic_id)
    cache_key = (resolved_clinic_id, key)
    cached = _SETTING_CACHE.get(cache_key)
    if cached is not None:
        cached_value, cached_at = cached
        if (datetime.utcnow() - cached_at).total_seconds() < CACHE_TTL_SECONDS:
            return cached_value

    result = await db.execute(
        select(ClinicSetting)
        .where(ClinicSetting.clinic_id == resolved_clinic_id)
        .where(ClinicSetting.key == key)
    )
    setting = result.scalar_one_or_none()

    if setting is None:
        return default

    _SETTING_CACHE[cache_key] = (setting.value, datetime.utcnow())
    return setting.value


async def set_setting(
    key: str,
    value: Any,
    db: AsyncSession,
    description: Optional[str] = None,
    clinic_id: Optional[int] = None,
) -> ClinicSetting:
    """Met à jour ou crée un paramètre clinique.
    Invalide le cache Redis.

    Args:
        key: Clé du paramètre
        value: Valeur (sera stockée en JSON)
        db: Session async SQLAlchemy
        description: Description optionnelle

    Returns:
        L'objet ClinicSetting créé/mis à jour
    """
    resolved_clinic_id = _resolve_clinic_id(clinic_id)
    normalized_value = _normalize_setting_value(value)

    result = await db.execute(
        select(ClinicSetting)
        .where(ClinicSetting.clinic_id == resolved_clinic_id)
        .where(ClinicSetting.key == key)
    )
    setting = result.scalar_one_or_none()

    if setting is None:
        setting = ClinicSetting(
            clinic_id=resolved_clinic_id,
            key=key,
            value=normalized_value,
            description=description,
        )
        db.add(setting)
    else:
        setting.value = normalized_value
        if description:
            setting.description = description

    await db.flush()
    await db.commit()
    await db.refresh(setting)

    _SETTING_CACHE.pop((resolved_clinic_id, key), None)

    return setting


async def get_all_settings(
    db: AsyncSession,
    clinic_id: Optional[int] = None,
) -> dict:
    """Retourne tous les paramètres sous forme de dict {key: value}."""
    resolved_clinic_id = _resolve_clinic_id(clinic_id)
    result = await db.execute(
        select(ClinicSetting).where(ClinicSetting.clinic_id == resolved_clinic_id)
    )
    settings = result.scalars().all()

    return {s.key: s.value for s in settings}
