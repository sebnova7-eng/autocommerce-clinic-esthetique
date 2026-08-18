"""
AutoCommerce Clinic — Configuration Celery + tâches planifiées
"""

from celery import Celery
from celery.schedules import crontab
from config import get_settings

settings = get_settings()

celery = Celery(
    "autocommerce_clinic",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=[
        "services.celery_app",
    ],
)

celery.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Africa/Tunis",
    enable_utc=True,
    # Bloc 19 : éviter la perte silencieuse et les exécutions sans borne.
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    task_track_started=True,
    task_time_limit=300,
    task_soft_time_limit=270,
    result_expires=86400,
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=100,
    worker_max_memory_per_child=400000,
    broker_connection_retry_on_startup=True,
    task_acks_on_failure_or_timeout=True,
    task_annotations={
        "services.celery_app.extract_facture_ia_task": {
            "rate_limit": "10/m",
            "soft_time_limit": 180,
            "time_limit": 210,
        },
    },
    beat_schedule={
        "reminder-j1": {
            "task": "services.celery_app.reminder_j1_task",
            "schedule": crontab(hour=18, minute=0),
        },
        "reminder-h2": {
            "task": "services.celery_app.reminder_h2_task",
            "schedule": crontab(minute="*/30"),
        },
        "check-stock-alerts": {
            "task": "services.celery_app.stock_alerts_task",
            "schedule": crontab(hour=8, minute=0),
        },
        "check-anniversaire": {
            "task": "services.celery_app.anniversaire_task",
            "schedule": crontab(hour=9, minute=0),
        },
        "check-inactivite": {
            "task": "services.celery_app.inactivite_task",
            "schedule": crontab(day_of_month=1, hour=10, minute=0),
        },
        "expire-points": {
            "task": "services.celery_app.expire_points_task",
            "schedule": crontab(day_of_month=1, hour=2, minute=0),
        },
        "calcul-commissions-mois": {
            "task": "services.celery_app.calcul_commissions_task",
            "schedule": crontab(day_of_month=1, hour=3, minute=0),
        },
        "injection-reminder": {
            "task": "services.celery_app.injection_reminder_task",
            "schedule": crontab(hour=9, minute=30),
        },
    },
)


# ── Tâches ─────────────────────────────────────────────────

@celery.task
def extract_facture_ia_task(depense_id: int):
    """Tâche Celery : extraction IA d'une facture."""
    import asyncio
    from services.facture_scanner import extract_facture_ia
    from models.database import get_async_engine, get_async_sessionmaker

    async def run():
        engine = get_async_engine(settings.database_url)
        session_factory = get_async_sessionmaker(engine)
        async with session_factory() as db:
            try:
                await extract_facture_ia(depense_id, db)
                await db.commit()
            except Exception:
                await db.rollback()
                raise

    asyncio.run(run())


@celery.task
def reminder_j1_task():
    """Rappel J-1 à 18h00."""
    import asyncio
    from services.agenda import reminder_j1
    from models.database import get_async_engine, get_async_sessionmaker

    async def run():
        engine = get_async_engine(settings.database_url)
        session_factory = get_async_sessionmaker(engine)
        async with session_factory() as db:
            await reminder_j1(db)

    asyncio.run(run())


@celery.task
def reminder_h2_task():
    """Rappel H-2 toutes les 30 minutes."""
    import asyncio
    from services.agenda import reminder_h2
    from models.database import get_async_engine, get_async_sessionmaker

    async def run():
        engine = get_async_engine(settings.database_url)
        session_factory = get_async_sessionmaker(engine)
        async with session_factory() as db:
            await reminder_h2(db)

    asyncio.run(run())


@celery.task
def stock_alerts_task():
    """Alertes stock quotidiennes, isolées par clinique."""
    import asyncio
    from services.alertes_stock import send_stock_alerts_whatsapp
    from models.database import get_async_engine, get_async_sessionmaker, Utilisateur
    from sqlalchemy import select

    async def run():
        engine = get_async_engine(settings.database_url)
        session_factory = get_async_sessionmaker(engine)
        async with session_factory() as db:
            clinic_rows = await db.execute(
                select(Utilisateur.clinic_id)
                .where(Utilisateur.is_active)
                .distinct()
            )
            for (clinic_id,) in clinic_rows.all():
                await send_stock_alerts_whatsapp(db, clinic_id=clinic_id)

    asyncio.run(run())


@celery.task
def anniversaire_task():
    """Vérification anniversaires quotidienne."""
    import asyncio
    from services.fidelite_clinic import check_anniversaire
    from models.database import get_async_engine, get_async_sessionmaker

    async def run():
        engine = get_async_engine(settings.database_url)
        session_factory = get_async_sessionmaker(engine)
        async with session_factory() as db:
            await check_anniversaire(db)

    asyncio.run(run())


@celery.task
def inactivite_task():
    """Relance inactivité mensuelle."""
    import asyncio
    from services.fidelite_clinic import check_inactivite
    from models.database import get_async_engine, get_async_sessionmaker

    async def run():
        engine = get_async_engine(settings.database_url)
        session_factory = get_async_sessionmaker(engine)
        async with session_factory() as db:
            await check_inactivite(db)

    asyncio.run(run())


@celery.task
def expire_points_task():
    """Expiration points mensuelle."""
    import asyncio
    from services.fidelite_clinic import expire_points
    from models.database import get_async_engine, get_async_sessionmaker

    async def run():
        engine = get_async_engine(settings.database_url)
        session_factory = get_async_sessionmaker(engine)
        async with session_factory() as db:
            await expire_points(db)

    asyncio.run(run())


@celery.task
def calcul_commissions_task():
    """Calcul commissions mensuel."""
    import asyncio
    from services.commissions import calculer_commissions_mois
    from models.database import get_async_engine, get_async_sessionmaker
    from datetime import date

    async def run():
        engine = get_async_engine(settings.database_url)
        session_factory = get_async_sessionmaker(engine)
        async with session_factory() as db:
            # Calculer pour le mois précédent
            today = date.today()
            mois_precedent = date(today.year, today.month - 1, 1) if today.month > 1 else date(today.year - 1, 12, 1)

            from sqlalchemy import select
            from models.database import Utilisateur, RoleEnum
            result = await db.execute(
                select(Utilisateur).where(Utilisateur.role == RoleEnum.COMMERCIAL.value)
            )
            commerciaux = result.scalars().all()

            for commercial in commerciaux:
                await calculer_commissions_mois(commercial.id, mois_precedent, db)

    asyncio.run(run())

@celery.task
def injection_reminder_task():
    """Rappels injections quotidiens à 9h30."""
    import asyncio
    from services.rappels_injection import process_injection_reminders
    from models.database import get_async_engine, get_async_sessionmaker

    async def run():
        engine = get_async_engine(settings.database_url)
        session_factory = get_async_sessionmaker(engine)
        async with session_factory() as db:
            await process_injection_reminders(db)

    asyncio.run(run())
