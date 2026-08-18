"""
AutoCommerce Clinic — Contexte clinique (multi-clinique préparation)
Injection automatique de clinic_id=1 sur toutes les requêtes
"""

from contextvars import ContextVar
from typing import Optional

clinic_id_var: ContextVar[Optional[int]] = ContextVar("clinic_id", default=None)


def get_current_clinic_id() -> int:
    """Retourne l'ID clinique courant, ou échoue si le middleware ne l'a pas établi."""
    clinic_id = clinic_id_var.get()
    if clinic_id is None:
        raise RuntimeError("Contexte clinique absent pour cette requête")
    return clinic_id


def set_clinic_id(clinic_id: int):
    """Définit l'ID clinique pour le contexte courant."""
    if clinic_id <= 0:
        raise ValueError("clinic_id doit être un entier positif")
    clinic_id_var.set(clinic_id)
