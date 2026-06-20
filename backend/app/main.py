"""FastAPI application entrypoint.

`socket_app` is the ASGI callable uvicorn serves — it wraps `app` (HTTP) plus
the socket.io server (WebSocket):

    uvicorn app.main:socket_app --reload --port 8000

Feature routers (auth, sessions, zoom, ...) are included in `create_app` as
Dev A and Dev B build them.
"""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
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

    @app.middleware("http")
    async def cross_origin_isolation(request: Request, call_next):
        """COOP/COEP — required for the Zoom SDK's SharedArrayBuffer/WASM.
        In local dev Vite sets these; in the bundled deploy the API serves the
        SPA, so the headers must come from here."""
        response = await call_next(request)
        response.headers["Cross-Origin-Opener-Policy"] = "same-origin"
        response.headers["Cross-Origin-Embedder-Policy"] = "require-corp"
        return response

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
        admin,
        analytics,
        assignments,
        auth,
        courses,
        dashboard,
        leaderboard,
        live,
        notes,
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
    app.include_router(notes.router, prefix="/api")
    app.include_router(dashboard.router, prefix="/api")
    app.include_router(analytics.router, prefix="/api")
    app.include_router(admin.router, prefix="/api")
    app.include_router(admin.public_router, prefix="/api")

    _mount_frontend(app)
    return app


def _mount_frontend(app: FastAPI) -> None:
    """Serve the built SPA from the API origin (same-origin → cookies/CORS just
    work). No-op in local dev where FRONTEND_DIST is unset and Vite serves it.
    """
    dist = Path(settings.FRONTEND_DIST) if settings.FRONTEND_DIST else None
    if not (dist and dist.is_dir()):
        return

    app.mount("/assets", StaticFiles(directory=str(dist / "assets")), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa(full_path: str) -> FileResponse:
        # API/socket paths are handled above (socket.io sits outside FastAPI);
        # anything else falls back to index.html so client-side routing works.
        if full_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="Not found")
        candidate = dist / full_path
        if full_path and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(dist / "index.html")


app = create_app()

# ASGI callable served by uvicorn — FastAPI + socket.io combined.
socket_app = mount(app)
