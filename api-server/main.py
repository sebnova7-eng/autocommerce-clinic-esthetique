"""
AutoCommerce Clinic — Point d'entrée FastAPI

Ce fichier n'existait pas : l'API ne pouvait pas démarrer. Il monte
les routers de api/v1, expose /health (attendu par le healthcheck
Docker de docker-compose.clinic.yml), configure CORS, et ferme
proprement le pool de connexions DB à l'arrêt.
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import Response
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import get_settings
from api.v1 import api_router
from api.deps import dispose_engine, limiter, get_db
from middleware.clinic_rbac import require_role
from models.database import RoleEnum


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await dispose_engine()


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="AutoCommerce Clinic API",
        version="1.0.0",
        lifespan=lifespan,
    )

    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
    allow_origins = ["*"] if settings.cors_origins.strip() == "*" else origins
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allow_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(api_router)

    settings.branding_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/static/branding", StaticFiles(directory=str(settings.branding_dir)), name="branding")

    @app.get("/health", tags=["health"])
    async def health():
        return {"status": "ok"}

    @app.get("/ready", tags=["health"])
    async def readiness(db: AsyncSession = Depends(get_db)):
        """Vérifie PostgreSQL et Redis sans divulguer les détails internes."""
        import logging
        from redis.asyncio import from_url as redis_from_url

        logger = logging.getLogger(__name__)
        postgres_ok = False
        redis_ok = False
        redis_client = None
        try:
            await db.execute(select(1))
            postgres_ok = True
            redis_client = redis_from_url(settings.redis_url, decode_responses=True)
            await redis_client.ping()
            redis_ok = True
        except Exception:
            logger.warning("Readiness dependency check failed", exc_info=True)
        finally:
            if redis_client is not None:
                try:
                    await redis_client.aclose()
                except Exception:
                    logger.debug("Redis readiness client close failed", exc_info=True)

        if postgres_ok and redis_ok:
            return {"status": "ready", "postgres": "ok", "redis": "ok"}
        return JSONResponse(status_code=503, content={"status": "not_ready"})

    @app.get("/metrics", tags=["health"])
    async def metrics(current_user: dict = Depends(require_role(RoleEnum.ADMIN, RoleEnum.DIRECTRICE))):
        """Endpoint Prometheus — retourne les métriques instrumentation."""
        from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
        return Response(
            content=generate_latest(),
            media_type=CONTENT_TYPE_LATEST,
        )

    # Instrumentation Prometheus (si Sentry/monitoring configuré)
    try:
        from prometheus_fastapi_instrumentator import Instrumentator
        # La route /metrics applicative reste protégée par RBAC ; ne pas
        # appeler expose(), qui ajouterait une route Prometheus publique.
        Instrumentator().instrument(app)
    except Exception:
        pass  # Prometheus non critique

    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)
