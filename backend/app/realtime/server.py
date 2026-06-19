"""python-socketio ASGI server.

`socket_app` wraps the FastAPI app so both HTTP and WebSocket traffic are
served by one ASGI callable (`uvicorn app.main:socket_app`). The Redis manager
lets multiple API instances share rooms — required for horizontal scaling.

Connection lifecycle:
  - connect: authenticate from the session cookie; reject anonymous sockets.
  - join_session: enter the class / private / (instructor) rooms.
  - caption_received: buffer the live transcript line in Redis.

Feature event handlers (M3) register against `sio` in dedicated modules.
"""

import redis.asyncio as aioredis
import socketio

from app.core.config import settings
from app.db.session import AsyncSessionLocal
from app.models.course import ClassSession
from app.models.user import User, UserRole
from app.realtime.auth import resolve_user_id_from_environ
from app.realtime.captions import buffer_caption
from app.realtime.rooms import compute_rooms

sio = socketio.AsyncServer(
    async_mode="asgi",
    client_manager=socketio.AsyncRedisManager(settings.REDIS_URL),
    cors_allowed_origins=settings.cors_origins,
)

_redis = aioredis.from_url(settings.REDIS_URL, decode_responses=True)


@sio.event
async def connect(sid: str, environ: dict, auth: dict | None = None) -> bool:
    """Accept only sockets carrying a valid session cookie."""
    user_id = resolve_user_id_from_environ(environ)
    if not user_id:
        return False  # rejects the connection
    await sio.save_session(sid, {"user_id": user_id})
    return True


@sio.event
async def join_session(sid: str, data: dict) -> None:
    session = await sio.get_session(sid)
    user_id = session.get("user_id")
    session_id = (data or {}).get("sessionId")
    if not user_id or not session_id:
        return

    async with AsyncSessionLocal() as db:
        user = await db.get(User, user_id)
        cs = await db.get(ClassSession, session_id)
    is_privileged = bool(
        user
        and (
            user.role in (UserRole.INSTRUCTOR, UserRole.ADMIN)
            or (cs is not None and cs.host_id == user_id)
        )
    )

    for room in compute_rooms(session_id, user_id, is_privileged=is_privileged):
        await sio.enter_room(sid, room)


@sio.event
async def caption_received(sid: str, data: dict) -> None:
    data = data or {}
    session_id = data.get("sessionId")
    text = data.get("text")
    if session_id and text:
        await buffer_caption(_redis, session_id, text, data.get("timestamp", 0))


@sio.event
async def disconnect(sid: str) -> None:
    return None


def mount(fastapi_app) -> socketio.ASGIApp:
    """Wrap the FastAPI app so socket.io shares the same ASGI server."""
    return socketio.ASGIApp(sio, other_asgi_app=fastapi_app)
