"""Tests — services/clinic_settings.py"""
import pytest
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import async_sessionmaker

from services.clinic_settings import get_all_settings, get_setting, set_setting


@pytest.mark.asyncio
async def test_get_setting_returns_default_when_missing(db):
    value = await get_setting("clinic.name", db, default="AutoCommerce Clinic")
    assert value == "AutoCommerce Clinic"


@pytest.mark.asyncio
async def test_set_then_get_setting_roundtrip(db):
    await set_setting("clinic.hours", {"open": "09:00", "close": "18:00"}, db)
    value = await get_setting("clinic.hours", db)
    assert value == {"open": "09:00", "close": "18:00"}


@pytest.mark.asyncio
async def test_set_setting_wraps_scalar_in_dict(db):
    await set_setting("clinic.max_photo_mb", 20, db)
    value = await get_setting("clinic.max_photo_mb", db)
    assert value == {"value": 20}


@pytest.mark.asyncio
async def test_set_setting_updates_existing_key(db):
    await set_setting("clinic.name", "Ancien Nom", db)
    await set_setting("clinic.name", "Nouveau Nom", db)
    value = await get_setting("clinic.name", db)
    assert value == {"value": "Nouveau Nom"}


@pytest.mark.asyncio
async def test_get_all_settings_returns_all_keys(db):
    await set_setting("a", 1, db)
    await set_setting("b", 2, db)
    all_settings = await get_all_settings(db)
    assert "a" in all_settings and "b" in all_settings


@pytest.mark.asyncio
async def test_set_setting_persists_across_sessions(engine):
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with session_factory() as session:
        await set_setting("clinic.name", "Test Clinic", session)

    async with session_factory() as another_session:
        value = await get_setting("clinic.name", another_session)
        assert value == {"value": "Test Clinic"}


@pytest.mark.asyncio
async def test_set_setting_rejects_non_json_payload(db):
    with pytest.raises(ValidationError):
        await set_setting("clinic.invalid", {"bad": {1, 2, 3}}, db)


@pytest.mark.asyncio
async def test_settings_are_isolated_between_clinics(db):
    await set_setting("clinic.name", "Clinic One", db, clinic_id=1)
    await set_setting("clinic.name", "Clinic Two", db, clinic_id=2)

    assert await get_setting("clinic.name", db, clinic_id=1) == {"value": "Clinic One"}
    assert await get_setting("clinic.name", db, clinic_id=2) == {"value": "Clinic Two"}
    assert await get_all_settings(db, clinic_id=1) == {"clinic.name": {"value": "Clinic One"}}
    assert await get_all_settings(db, clinic_id=2) == {"clinic.name": {"value": "Clinic Two"}}
