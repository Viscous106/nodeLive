"""Application settings, loaded from environment / .env via pydantic-settings.

Every value has a local-dev default so the app boots out of the box after
`docker compose up postgres redis`. Production overrides via real env vars.
"""

from functools import lru_cache

from pydantic import field_validator
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
    # Path to the built frontend (set in the Docker image to serve the SPA from
    # the API origin). Empty in local dev — Vite serves the frontend separately.
    FRONTEND_DIST: str = ""

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

    # --- Bootstrap admin (no-shell first admin on a fresh/deployed instance) ---
    # Comma-separated emails auto-granted ADMIN on signup/login. Solves the
    # chicken-and-egg of needing an admin to use the admin panel when there's no
    # shell to run `set_role`. Safe: it's an explicit allowlist, overridable via
    # the BOOTSTRAP_ADMIN_EMAILS env var.
    BOOTSTRAP_ADMIN_EMAILS: str = "abhinav.singh@scaler.com"

    # --- Zoom Meeting SDK ---
    ZOOM_SDK_KEY: str = ""
    ZOOM_SDK_SECRET: str = ""

    # --- Zoom webhooks + Server-to-Server OAuth (Reports API, recordings) ---
    ZOOM_WEBHOOK_SECRET_TOKEN: str = ""
    ZOOM_S2S_ACCOUNT_ID: str = ""
    ZOOM_S2S_CLIENT_ID: str = ""
    ZOOM_S2S_CLIENT_SECRET: str = ""
    # Delay before reconciling attendance against the Reports API, giving Zoom
    # time to finalize the participant report after the meeting ends.
    ATTENDANCE_RECONCILE_DELAY_SECS: int = 5 * 60

    # --- AI ---
    ANTHROPIC_API_KEY: str = ""
    ANTHROPIC_MODEL: str = "claude-sonnet-4-6"

    @field_validator("DATABASE_URL", "DIRECT_DATABASE_URL", mode="after")
    @classmethod
    def _force_asyncpg(cls, v: str | None) -> str | None:
        """Managed hosts (Fly/Render/Heroku) hand out `postgres://…` — coerce to
        the async driver SQLAlchemy/asyncpg need."""
        if not v:
            return v
        for prefix in ("postgresql+asyncpg://", "postgresql+psycopg://"):
            if v.startswith(prefix):
                return v
        if v.startswith("postgres://"):
            return v.replace("postgres://", "postgresql+asyncpg://", 1)
        if v.startswith("postgresql://"):
            return v.replace("postgresql://", "postgresql+asyncpg://", 1)
        return v

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGIN.split(",") if o.strip()]

    @property
    def bootstrap_admin_emails(self) -> set[str]:
        return {
            e.strip().lower()
            for e in self.BOOTSTRAP_ADMIN_EMAILS.split(",")
            if e.strip()
        }

    @property
    def alembic_url(self) -> str:
        return self.DIRECT_DATABASE_URL or self.DATABASE_URL


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
