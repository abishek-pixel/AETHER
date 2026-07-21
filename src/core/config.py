import os
import logging
from pydantic_settings import BaseSettings
from pydantic import field_validator
from functools import lru_cache

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    """Application settings — loaded from environment variables / .env file.

    Production (Render): every secret MUST be set as a Render environment variable.
    Local development:   values are read from the .env file (never committed).

    DATABASE_URL has NO localhost default in production.  The application will
    raise a clear error on startup if it is missing in production.
    """

    # ── LLM Providers ─────────────────────────────────────────────────────
    groq_api_key: str = ""
    google_api_key: str = ""
    ollama_base_url: str = "http://localhost:11434"

    # ── Default model names ───────────────────────────────────────────────
    default_text_model: str = "llama-3.3-70b-versatile"
    default_vision_model: str = "llava:13b"
    fallback_vision_model: str = "gemini-1.5-flash"

    # ── Search APIs ───────────────────────────────────────────────────────
    tavily_api_key: str = ""
    serper_api_key: str = ""
    hf_token: str = ""

    # ── PostgreSQL ────────────────────────────────────────────────────────
    # LOCAL:      set DATABASE_URL in your .env file
    # PRODUCTION: set DATABASE_URL in the Render dashboard (Environment section)
    #
    # The default empty string is intentional — if this is empty in production
    # the application will refuse to start rather than silently connecting nowhere.
    #
    # Render provides its PostgreSQL URL as:
    #   postgres://user:pass@host/db   (note: "postgres://" NOT "postgresql://")
    # The validator below normalises this automatically.
    database_url: str = ""

    @field_validator("database_url", mode="before")
    @classmethod
    def normalise_database_url(cls, v: str) -> str:
        """
        Normalise the DATABASE_URL for the asyncpg driver used at runtime.

        Handles:
          - Render's postgres://   → postgresql+asyncpg://
          - Plain postgresql://    → postgresql+asyncpg://
          - Already correct postgresql+asyncpg://  → unchanged
        """
        if not v:
            return v  # will be caught by startup validation
        # Render (and many providers) supply postgres:// — asyncpg needs postgresql+asyncpg://
        if v.startswith("postgres://"):
            v = v.replace("postgres://", "postgresql+asyncpg://", 1)
        elif v.startswith("postgresql://") and "+asyncpg" not in v:
            v = v.replace("postgresql://", "postgresql+asyncpg://", 1)
        return v

    # ── JWT Authentication ────────────────────────────────────────────────
    # IMPORTANT: override SECRET_KEY with a strong random value in production.
    # Generate: python -c "import secrets; print(secrets.token_hex(32))"
    secret_key: str = "CHANGE_ME_USE_SECRETS_TOKEN_HEX_32_IN_PRODUCTION"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    refresh_token_expire_days: int = 30

    # ── Neo4j (optional) ──────────────────────────────────────────────────
    neo4j_uri: str = "neo4j+s://localhost"
    neo4j_user: str = "neo4j"
    neo4j_password: str = ""

    # ── Qdrant (optional) ─────────────────────────────────────────────────
    qdrant_host: str = "localhost"
    qdrant_port: int = 6333
    qdrant_api_key: str = ""
    qdrant_url: str = ""

    # ── Redis (optional) ─────────────────────────────────────────────────
    redis_url: str = "redis://localhost:6379"

    # ── CORS / Frontend origin ────────────────────────────────────────────
    # Set FRONTEND_URL to your Vercel deployment URL in production.
    # Multiple origins can be comma-separated: https://a.vercel.app,https://b.com
    frontend_url: str = ""

    # ── Application limits ────────────────────────────────────────────────
    max_iterations: int = 5
    confidence_threshold: float = 0.7
    cost_limit_per_session: float = 1.0
    requests_per_minute: int = 60

    # ── Deployment flag ───────────────────────────────────────────────────
    # Set ENVIRONMENT=production on Render.
    environment: str = "development"

    # Pydantic v2 config
    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",    # tolerate extra OS env vars (PATH, HF_TOKEN, etc.)
        "case_sensitive": False,
    }


@lru_cache()
def get_settings() -> Settings:
    settings = Settings()

    # ── Production guard — refuse to start without a real DATABASE_URL ──
    if settings.environment == "production" and not settings.database_url:
        raise RuntimeError(
            "DATABASE_URL is not set. "
            "Configure it in the Render dashboard: "
            "AETHER-BACKEND → Environment → DATABASE_URL"
        )

    # Warn in development if still using the default (localhost might not be running)
    if settings.environment != "production" and not settings.database_url:
        logger.warning(
            "DATABASE_URL is not set — using localhost default. "
            "Set DATABASE_URL in your .env file for local development."
        )
        # Fall back to localhost only in development
        object.__setattr__(
            settings,
            "database_url",
            "postgresql+asyncpg://postgres:password@localhost:5432/aether",
        )

    return settings
