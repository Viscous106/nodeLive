"""Application settings, loaded from environment / .env via pydantic-settings.

Every value has a local-dev default so the app boots out of the box after
`docker compose up postgres redis`. Production overrides via real env vars.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- App ---
    APP_NAME: str = "linkHQ"
    ENV: str = "development"
    DEBUG: bool = True

    # --- Database ---
    # Async URL used by the app (goes through PgBouncer in prod).
    DATABASE_URL: str = (
        "postgresql+asyncpg://edustream:localdev@localhost:5432/edustream"
    )
    # Direct URL for Alembic DDL (bypasses PgBouncer). Defaults to DATABASE_URL.
    DIRECT_DATABASE_URL: str | None = None

    # --- Redis (socket.io adapter + Celery broker) ---
    REDIS_URL: str = "redis://localhost:6379/0"

    # --- CORS / cookies ---
    CORS_ORIGIN: str = "http://localhost:5173"

    # --- Auth ---
    AUTH_SECRET: str = "dev-insecure-change-me"
    ACCESS_TOKEN_TTL_MINUTES: int = 60 * 24 * 7  # 7 days
    COOKIE_NAME: str = "linkhq_session"
    COOKIE_SECURE: bool = False  # True in production (HTTPS only)

    # --- Zoom Meeting SDK ---
    ZOOM_SDK_KEY: str = ""
    ZOOM_SDK_SECRET: str = ""

    # --- AI ---
    ANTHROPIC_API_KEY: str = ""
    ANTHROPIC_MODEL: str = "claude-sonnet-4-6"

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGIN.split(",") if o.strip()]

    @property
    def alembic_url(self) -> str:
        return self.DIRECT_DATABASE_URL or self.DATABASE_URL


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
