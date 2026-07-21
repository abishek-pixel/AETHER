"""
Alembic environment — synchronous psycopg2 migrations.

Works for both local development and Render-hosted PostgreSQL.

URL normalisation:
  - Render supplies:  postgres://...   (no driver prefix)
  - asyncpg runtime: postgresql+asyncpg://...
  - Alembic/psycopg2: postgresql+psycopg2://...

All three forms are normalised here from the single DATABASE_URL env var.
"""
import os
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool
from alembic import context

# ── Register all ORM models so autogenerate can detect schema changes ──────
from src.database.session import Base
import src.models  # noqa: F401  — side-effect: registers all models with Base

from src.core.config import get_settings

settings = get_settings()
config = context.config

# ── Derive psycopg2 (sync) URL from the canonical DATABASE_URL ────────────
# At this point settings.database_url is already normalised to postgresql+asyncpg://
# (or postgresql+asyncpg:// if it came from postgres://) — we just swap the driver.
raw_url: str = settings.database_url

# Ensure we start from the canonical postgresql:// base before adding driver
# (handle any edge case where the URL might still be postgres://)
if raw_url.startswith("postgres://"):
    raw_url = raw_url.replace("postgres://", "postgresql://", 1)

sync_url: str = (
    raw_url
    .replace("postgresql+asyncpg://", "postgresql+psycopg2://", 1)
    .replace("postgresql+psycopg://", "postgresql+psycopg2://", 1)
)
if sync_url.startswith("postgresql://") and "+psycopg" not in sync_url:
    sync_url = sync_url.replace("postgresql://", "postgresql+psycopg2://", 1)

# configparser uses % for interpolation — escape literal % characters in the URL
config.set_main_option("sqlalchemy.url", sync_url.replace("%", "%%"))

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _engine_connect_args() -> dict:
    """Return sslmode=require for cloud PostgreSQL; nothing for localhost."""
    is_local = "localhost" in sync_url or "127.0.0.1" in sync_url
    if not is_local:
        # psycopg2 uses sslmode as a connect_arg (not ssl="require" like asyncpg)
        return {"connect_args": {"sslmode": "require"}}
    return {}


def run_migrations_offline() -> None:
    """Run migrations without a live DB connection (generates SQL script)."""
    context.configure(
        url=sync_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations against the live database."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
        url=sync_url,          # override the placeholder in alembic.ini
        **_engine_connect_args(),
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
