"""Tests — middleware/clinic_rbac.py

La matrice de permissions est la seule barrière entre les rôles
non-médicaux (assistante, commercial) et les dossiers médicaux /
photos. Ces tests verrouillent ce comportement.
"""
import pytest
from fastapi import HTTPException

from middleware.clinic_rbac import check_permission, require_role
from models.database import RoleEnum, Utilisateur


# ── Règles métier critiques (confidentialité médicale) ──────

@pytest.mark.parametrize("role", ["assistante", "commercial"])
def test_non_medical_roles_have_no_access_to_dossiers_medicaux(role):
    assert check_permission(role, "dossiers_medicaux", "read") is False
    assert check_permission(role, "dossiers_medicaux", "write") is False


def test_estheticienne_can_write_dossiers_but_matrix_does_not_scope_antecedents():
    """La restriction 'PAS antécédents' pour l'esthéticienne est documentée
    en commentaire mais n'est pas appliquée au niveau champ — check_permission
    ne connaît que read/write au niveau ressource. Ce test documente la limite
    actuelle : il faudra un filtrage au niveau des champs si on veut vraiment
    cacher les antécédents à l'esthéticienne."""
    assert check_permission("estheticienne", "dossiers_medicaux", "write") is True


def test_assistante_has_no_access_to_photos_medicales():
    assert check_permission("assistante", "photos", "read") is False


def test_directrice_cannot_read_encrypted_dossier_write():
    """DIRECTRICE : lecture seule sur dossiers_medicaux (pas d'accès
    contenu chiffré en écriture)."""
    assert check_permission("directrice", "dossiers_medicaux", "read") is True
    assert check_permission("directrice", "dossiers_medicaux", "write") is False


def test_medecin_full_access_to_dossiers():
    assert check_permission("medecin", "dossiers_medicaux", "read") is True
    assert check_permission("medecin", "dossiers_medicaux", "write") is True
    assert check_permission("medecin", "dossiers_medicaux", "delete") is False


def test_admin_has_delete_everywhere_defined():
    for resource in ("patients", "dossiers_medicaux", "photos", "stock_injectables"):
        assert check_permission("admin", resource, "delete") is True


def test_commercial_read_only_on_patients():
    assert check_permission("commercial", "patients", "read") is True
    assert check_permission("commercial", "patients", "write") is False


def test_commercial_has_no_access_to_stock():
    assert check_permission("commercial", "stock_injectables", "read") is False


# ── Robustesse générale ──────────────────────────────────────

def test_unknown_resource_denies_by_default():
    assert check_permission("admin", "resource_qui_n_existe_pas", "read") is False


def test_unknown_role_denies_by_default():
    assert check_permission("role_invente", "patients", "read") is False


def test_unknown_action_denies_by_default():
    assert check_permission("medecin", "dossiers_medicaux", "delete") is False


# ── require_role (dependency FastAPI) ────────────────────────

from unittest.mock import MagicMock

@pytest.mark.asyncio
async def test_require_role_allows_matching_role():
    checker = require_role(RoleEnum.MEDECIN, RoleEnum.DIRECTRICE)
    mock_user = MagicMock(spec=Utilisateur)
    mock_user.role = "medecin"
    mock_user.id = 1
    user = await checker(current_user=mock_user)
    assert user.role == "medecin"


@pytest.mark.asyncio
async def test_require_role_rejects_non_matching_role():
    checker = require_role(RoleEnum.MEDECIN)
    mock_user = MagicMock(spec=Utilisateur)
    mock_user.role = "assistante"
    mock_user.id = 1
    with pytest.raises(HTTPException) as exc:
        await checker(current_user=mock_user)
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_require_role_rejects_missing_role():
    checker = require_role(RoleEnum.MEDECIN)
    mock_user = MagicMock(spec=Utilisateur)
    mock_user.role = None
    mock_user.id = 1
    with pytest.raises(HTTPException) as exc:
        await checker(current_user=mock_user)
    assert exc.value.status_code == 401
