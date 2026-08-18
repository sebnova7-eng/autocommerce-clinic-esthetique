"""Tests du middleware de contexte clinique fail-closed."""
import pytest

from middleware.clinic_context import get_current_clinic_id, set_clinic_id


def test_missing_clinic_id_fails_closed():
    with pytest.raises(RuntimeError, match="Contexte clinique absent"):
        get_current_clinic_id()


def test_set_clinic_id_changes_current_context():
    set_clinic_id(7)
    try:
        assert get_current_clinic_id() == 7
    finally:
        set_clinic_id(1)
