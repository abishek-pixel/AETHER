"""
Async SQLAlchemy engine, session factory, and Base.

Architecture:
  - Runtime (FastAPI):  asyncpg driver  (postgresql+asyncpg://)
  - Migrations (Alembic): psycopg2 driver  (postgresql+psycopg2://)

The engine is created lazily (on first use) so that the /health endpoint
can respond immediately without waiting for a database connection.
"""
from __future__ import annotations

import logging
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
    AsyncEngine,
)
from sqlalchemy.orm import DeclarativeBase

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    pass


# ── Lazy engine — created on first use, not at module import time ──────────
_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker | None = None


def _get_engine() -> AsyncEngine:
    """Return the shared engine, creating it if necessary."""
    global _engine, _session_factory
    if _engine is not None:
        return _engine

    from src.core.config import get_settings
    settings = get_settings()

    url = settings.database_url
    if not url:
        raise RuntimeError(
            "DATABASE_URL is not configured. "
            "Set it as an environment variable before starting the server."
        )

    # ── Connection pool settings ──────────────────────────────────────────
    # Conservative values suitable for Render starter plan (max 25 connections).
    # pool_size=5 + max_overflow=5 = up to 10 total connections under load.
    kwargs: dict = {
        "echo": False,
        "pool_size": 5,
        "max_overflow": 5,
        # Validate connections before checkout — recovers from DB restarts / idle timeouts.
        "pool_pre_ping": True,
        # Recycle connections after 30 min to avoid stale-connection errors.
        "pool_recycle": 1800,
    }

    # ── SSL for cloud PostgreSQL (Render, Supabase, etc.) ─────────────────
    # asyncpg uses connect_args={"ssl": "require"} not sslmode query param.
    is_local = "localhost" in url or "127.0.0.1" in url
    if not is_local:
        kwargs["connect_args"] = {"ssl": "require"}

    _engine = create_async_engine(url, **kwargs)
    _session_factory = async_sessionmaker(
        bind=_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
        autocommit=False,
    )
    return _engine


def get_session_factory() -> async_sessionmaker:
    _get_engine()   # ensures _session_factory is initialised
    assert _session_factory is not None
    return _session_factory


# ── Legacy module-level aliases (used by existing code) ───────────────────
# These properties delegate to the lazy getter so module-level imports still work.

class _LazyEngine:
    """Proxy that initialises the real engine on first attribute access."""
    def __getattr__(self, name: str):
        return getattr(_get_engine(), name)

    def __call__(self, *args, **kwargs):
        return _get_engine()(*args, **kwargs)


# Expose engine and AsyncSessionLocal at module level for backward compat
class _EngineProxy:
    def __getattr__(self, name):
        return getattr(_get_engine(), name)

engine = _EngineProxy()  # type: ignore[assignment]


class _SessionProxy:
    """Makes AsyncSessionLocal() work as a context manager."""
    def __call__(self, *args, **kwargs):
        return get_session_factory()(*args, **kwargs)

    def __getattr__(self, name):
        return getattr(get_session_factory(), name)


AsyncSessionLocal = _SessionProxy()  # type: ignore[assignment]


# ── FastAPI dependency ─────────────────────────────────────────────────────

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that yields an async database session."""
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# ── Startup helper ─────────────────────────────────────────────────────────

async def init_db() -> None:
    """
    Ensure all ORM tables exist.

    Called on application startup.  Safe to run repeatedly — creates only
    tables that are missing.  Alembic handles proper schema migrations.

    Does NOT block the /health endpoint because the engine is created lazily.
    """
    eng = _get_engine()
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
