"""
AutoCommerce Clinic — Alembic env.py

Génère/applique les migrations à partir des modèles SQLAlchemy de
models/database.py. Supporte le mode "offline" (génère le SQL sans
connexion) et "online" (connexion réelle, utilisée en sync via
create_engine — asyncpg n'est utilisé que côté app, pas ici).
"""

import os
import sys
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

# Rend importable models/, config.py, etc. (api-server/ est déjà dans
# prepend_sys_path via alembic.ini, mais on le fixe explicitement aussi)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def _load_env_file() -> None:
    """Charge ENV_FILE ou .env.clinic pour rendre Alembic reproductible.
    Les variables déjà exportées restent prioritaires."""
    candidate = os.environ.get("ENV_FILE") or os.path.join(os.path.dirname(__file__), "..", ".env.clinic")
    if not os.path.isfile(candidate):
        return
    with open(candidate, encoding="utf-8") as env_file:
        for raw_line in env_file:
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip("\\\"'")
            if key and key not in os.environ:
                os.environ[key] = value


_load_env_file()

from config import get_settings  # noqa: E402
from models.database import Base  # noqa: E402

# Importer tous les modules contenant des modèles pour que Base.metadata
# soit complète avant autogenerate. Sans ces imports, Alembic interprète à
# tort les tables workflow, sécurité et omnicanal comme supprimées.
from models import omnicanal as _omnicanal_models  # noqa: E402,F401
from models import security as _security_models  # noqa: E402,F401
from models import workflow_engine as _workflow_models  # noqa: E402,F401

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def get_url() -> str:
    """URL de connexion : var d'env DATABASE_URL/.env.clinic en priorité,
    sinon la valeur d'alembic.ini. Convertit le driver asyncpg -> psycopg2
    (synchrone) car Alembic tourne ici en mode sync classique."""
    settings = get_settings()
    url = settings.database_url or config.get_main_option("sqlalchemy.url")
    # Conversion drivers async -> sync pour Alembic
    url = url.replace("+asyncpg", "+psycopg2")
    url = url.replace("+aiosqlite", "")
    return url


def run_migrations_offline() -> None:
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = get_url()

    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
