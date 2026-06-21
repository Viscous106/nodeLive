"""Application settings, loaded from environment / .env via pydantic-settings.

Every value has a local-dev default so the app boots out of the box after
`docker compose up postgres redis`. Production overrides via real env vars.
"""

import os
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
    BOOTSTRAP_ADMIN_EMAILS: str = "abhinav.singh@scaler.com,yash.virulkar@scaler.com"

    # --- Zoom Meeting SDK ---
    ZOOM_SDK_KEY: str = ""
    ZOOM_SDK_SECRET: str = ""

    # --- Zoom webhooks + Server-to-Server OAuth (Reports API, recordings) ---
    ZOOM_WEBHOOK_SECRET_TOKEN: str = ""
    ZOOM_S2S_ACCOUNT_ID: str = ""
    ZOOM_S2S_CLIENT_ID: str = ""
    ZOOM_S2S_CLIENT_SECRET: str = ""
    # Zoom user (email or userId) that hosts auto-created class meetings and whose
    # ZAK lets an instructor START a meeting from inside the app. S2S has no "me",
    # so this must be a real user on the Zoom account.
    ZOOM_HOST_EMAIL: str = ""
    # Delay before reconciling attendance against the Reports API, giving Zoom
    # time to finalize the participant report after the meeting ends.
    ATTENDANCE_RECONCILE_DELAY_SECS: int = 5 * 60

    # --- Recording storage (Cloudflare R2 / S3-compatible) ---
    # All empty by default → ingest + presign raise/501 (graceful degrade).
    R2_ACCOUNT_ID: str = ""
    R2_ACCESS_KEY_ID: str = ""
    R2_SECRET_ACCESS_KEY: str = ""
    R2_BUCKET: str = ""
    # e.g. https://<account_id>.r2.cloudflarestorage.com
    R2_ENDPOINT_URL: str = ""
    # Presigned playback URL lifetime.
    RECORDING_URL_TTL_SECS: int = 300

    # --- Email (SMTP) ---
    # All empty by default → send silently skipped (graceful degrade).
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USERNAME: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM: str = "noreply@linkhq.app"

    # --- AI ---
    # Primary provider: Anthropic Claude. Fallback: Groq (OpenAI-compatible) when
    # ANTHROPIC_API_KEY is unset or a call fails. If neither is set the AI routes
    # degrade gracefully (501). See plan.md §7.4a. (Fallback wiring is pending.)
    ANTHROPIC_API_KEY: str = ""
    ANTHROPIC_MODEL: str = "claude-sonnet-4-6"
    GROQ_API_KEY: str = ""
    GROQ_MODEL: str = "llama-3.3-70b-versatile"

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
        origins = [o.strip() for o in self.CORS_ORIGIN.split(",") if o.strip()]
        # Render injects the service's public URL. Include it so the same-origin
        # SPA's WebSocket (socket.io) handshake isn't rejected with 403 in prod
        # (socket.io enforces cors_allowed_origins on the Origin header).
        render_url = os.environ.get("RENDER_EXTERNAL_URL", "").strip()
        if render_url and render_url not in origins:
            origins.append(render_url)
        return origins

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
