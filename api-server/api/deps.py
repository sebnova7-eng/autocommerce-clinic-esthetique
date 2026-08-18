"""
AutoCommerce Clinic — Dépendance DB partagée

Un seul engine (donc un seul pool de connexions) pour tout le
process, créé une fois au premier appel puis réutilisé — au lieu de
recréer un engine à chaque requête (fuite de connexions garantie
sous charge).
"""
from functools import lru_cache

from sqlalchemy.ext.asyncio import AsyncSession
from slowapi import Limiter
from slowapi.util import get_remote_address

from config import get_settings
from models.database import get_async_engine, get_async_sessionmaker
from middleware.auth import get_current_user  # noqa: F401 – réexporté pour les routers
from middleware.clinic_rbac import require_role  # noqa: F401 – compat import routers historiques

limiter = Limiter(key_func=get_remote_address, enabled=get_settings().env != "test")


@lru_cache
def _get_engine():
    settings = get_settings()
    return get_async_engine(settings.database_url)


@lru_cache
def _get_sessionmaker():
    return get_async_sessionmaker(_get_engine())


async def get_db() -> AsyncSession:
    """Dépendance FastAPI : une session par requête, un engine par process."""
    session_factory = _get_sessionmaker()
    async with session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def dispose_engine():
    """À appeler à l'arrêt de l'app (lifespan) pour fermer proprement le pool."""
    if _get_engine.cache_info().currsize:
        await _get_engine().dispose()
