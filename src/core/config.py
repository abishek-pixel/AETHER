import os
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings — loaded from environment variables / .env file.

    Every field that has no default MUST be set in the environment before
    the application starts.  Fields with defaults are optional — the app
    starts without them but some features will be disabled.
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
    # Production value set as DATABASE_URL env var on Render.
    database_url: str = "postgresql+asyncpg://postgres:password@localhost:5432/aether"

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
    qdrant_api_key: str = ""          # required for Qdrant Cloud
    qdrant_url: str = ""              # alternative to host/port for cloud

    # ── Redis (optional — not yet used at runtime) ────────────────────────
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

    # ── Deployment ────────────────────────────────────────────────────────
    # Set to "production" on Render to tighten security defaults.
    environment: str = "development"

    # Pydantic v2 config
    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",   # tolerate extra env vars (e.g. HF_TOKEN, PATH) without crashing
        "case_sensitive": False,
    }


@lru_cache()
def get_settings() -> Settings:
    return Settings()
