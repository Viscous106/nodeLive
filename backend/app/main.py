"""FastAPI application entrypoint.

`socket_app` is the ASGI callable uvicorn serves — it wraps `app` (HTTP) plus
the socket.io server (WebSocket):

    uvicorn app.main:socket_app --reload --port 8000

Feature routers (auth, sessions, zoom, ...) are included in `create_app` as
Dev A and Dev B build them.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.core.config import settings
from app.db.session import engine
from app.realtime.server import mount


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Startup hooks (warm caches, etc.) go here.
    yield
    # Graceful shutdown — release the DB pool.
    await engine.dispose()


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.APP_NAME,
        debug=settings.DEBUG,
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,  # cookies for auth
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health", tags=["health"])
    async def health() -> dict[str, str]:
        """Liveness probe — no dependencies, always cheap."""
        return {"status": "ok", "app": settings.APP_NAME}

    @app.get("/health/ready", tags=["health"])
    async def readiness() -> dict[str, str]:
        """Readiness probe — verifies the database is reachable."""
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return {"status": "ready"}

    # Routers added here as features land:
    from app.api import (
        assignments,
        auth,
        courses,
        leaderboard,
        live,
        sessions,
        webhooks,
    )

    app.include_router(auth.router, prefix="/api")
    app.include_router(courses.router, prefix="/api")
    app.include_router(sessions.router, prefix="/api")
    app.include_router(assignments.router, prefix="/api")
    app.include_router(live.router, prefix="/api")
    app.include_router(webhooks.router, prefix="/api")
    app.include_router(leaderboard.router, prefix="/api")

    return app


app = create_app()

# ASGI callable served by uvicorn — FastAPI + socket.io combined.
socket_app = mount(app)
