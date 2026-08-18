"""Tests — api-server/bootstrap_admin.py (fonction bootstrap())"""

import pytest
from sqlalchemy import select

from bootstrap_admin import bootstrap  # noqa: E402
from models.database import Utilisateur, RoleEnum


@pytest.mark.asyncio
async def test_bootstrap_creates_active_directrice(db, engine, monkeypatch):
    # bootstrap() crée son propre engine ; on le fait pointer vers la même
    # base sqlite en mémoire que la fixture de test (StaticPool partagé).
    # On neutralise aussi dispose() : bootstrap() ferme "son" engine en fin
    # d'exécution, ce qui viderait la base en mémoire partagée par le test.
    import bootstrap_admin

    async def _noop_dispose(self):
        pass

    monkeypatch.setattr(bootstrap_admin, "create_async_engine", lambda url: engine)
    monkeypatch.setattr(type(engine), "dispose", _noop_dispose)

    await bootstrap("nouvelle@clinic.tn", "Kallel", "Dorra", "MotDePasseSolide123", RoleEnum.DIRECTRICE.value)

    from sqlalchemy.ext.asyncio import async_sessionmaker
    sessionmaker = async_sessionmaker(engine, expire_on_commit=False)
    async with sessionmaker() as session:
        result = await session.execute(select(Utilisateur).where(Utilisateur.email == "nouvelle@clinic.tn"))
        user = result.scalar_one_or_none()
        assert user is not None
        assert user.role == RoleEnum.DIRECTRICE.value
        assert user.is_active is True
        assert user.hashed_password != "MotDePasseSolide123"


@pytest.mark.asyncio
async def test_bootstrap_skips_if_email_already_exists(db, engine, monkeypatch, capsys):
    import bootstrap_admin

    async def _noop_dispose(self):
        pass

    monkeypatch.setattr(bootstrap_admin, "create_async_engine", lambda url: engine)
    monkeypatch.setattr(type(engine), "dispose", _noop_dispose)

    await bootstrap("dup@clinic.tn", "A", "B", "MotDePasseSolide123", RoleEnum.DIRECTRICE.value)
    await bootstrap("dup@clinic.tn", "A", "B", "AutreMotDePasse456", RoleEnum.DIRECTRICE.value)

    captured = capsys.readouterr()
    assert "existe déjà" in captured.out
