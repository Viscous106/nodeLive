"""python-socketio ASGI server.

`socket_app` wraps the FastAPI app so both HTTP and WebSocket traffic are
served by one ASGI callable (`uvicorn app.main:socket_app`). The Redis manager
lets multiple API instances share rooms — required for horizontal scaling.

Feature event handlers (Dev B) live in dedicated modules and register against
`sio` (e.g. `@sio.on("poll:vote")`). This module only owns connection lifecycle.
"""

import socketio

from app.core.config import settings

sio = socketio.AsyncServer(
    async_mode="asgi",
    client_manager=socketio.AsyncRedisManager(settings.REDIS_URL),
    cors_allowed_origins=settings.cors_origins,
)


@sio.event
async def connect(sid: str, environ: dict, auth: dict | None = None) -> None:
    """Accept a socket connection. Auth/identity wiring is added by Dev B."""
    return None


@sio.event
async def disconnect(sid: str) -> None:
    return None


def mount(fastapi_app) -> socketio.ASGIApp:
    """Wrap the FastAPI app so socket.io shares the same ASGI server."""
    return socketio.ASGIApp(sio, other_asgi_app=fastapi_app)
