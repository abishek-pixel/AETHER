"""Async SQLAlchemy engine, session factory, and Base."""
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from src.core.config import get_settings

settings = get_settings()


class Base(DeclarativeBase):
    pass


def _build_engine_kwargs() -> dict:
    """Build engine kwargs — adds SSL args for Render-hosted PostgreSQL."""
    kwargs: dict = {
        "echo": False,
        "pool_size": 10,
        "max_overflow": 20,
        # Validate connections before use — prevents stale-connection errors
        # after PostgreSQL restarts or idle-connection timeouts.
        "pool_pre_ping": True,
        "pool_recycle": 1800,   # recycle connections every 30 min
    }
    # Render (and most cloud PG providers) require SSL.
    # asyncpg accepts ssl="require" via connect_args.
    url = settings.database_url
    if "localhost" not in url and "127.0.0.1" not in url:
        kwargs["connect_args"] = {"ssl": "require"}
    return kwargs


engine = create_async_engine(
    settings.database_url,
    **_build_engine_kwargs(),
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)


async def get_db() -> AsyncSession:
    """FastAPI dependency that yields a database session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db() -> None:
    """Create all tables that do not yet exist.

    Called on application startup.  Safe to run repeatedly — Alembic handles
    schema migrations; this call just ensures tables exist for the very first
    boot before migrations have run.
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
