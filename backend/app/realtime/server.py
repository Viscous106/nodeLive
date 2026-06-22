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

from datetime import UTC, datetime

import redis.asyncio as aioredis
import socketio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import AsyncSessionLocal
from app.models.attendance import SessionPresence
from app.models.course import ClassSession, Enrollment
from app.models.user import User, UserRole
from app.realtime.auth import resolve_user_id_from_environ
from app.realtime.captions import buffer_caption
from app.realtime.rooms import compute_rooms, instructor_room, session_room

sio = socketio.AsyncServer(
    async_mode="asgi",
    client_manager=socketio.AsyncRedisManager(settings.REDIS_URL),
    cors_allowed_origins=settings.cors_origins,
)

_redis = aioredis.from_url(settings.REDIS_URL, decode_responses=True)

# sid → SessionPresence.id, so `disconnect` can close the row opened on join.
# TTL guards against a leaked row if a disconnect is ever missed.
_PRESENCE_KEY = "presence:sid:{sid}"
_PRESENCE_TTL = 60 * 60 * 12  # 12h


async def _close_presence(presence_id: str) -> None:
    async with AsyncSessionLocal() as db:
        pres = await db.get(SessionPresence, presence_id)
        if pres is not None and pres.left_at is None:
            pres.left_at = datetime.now(UTC)
            await db.commit()


async def _open_presence(sid: str, session_id: str, user_id: str) -> None:
    """Record a join. Close any still-open row for this sid first (re-join)."""
    prev = await _redis.get(_PRESENCE_KEY.format(sid=sid))
    if prev:
        await _close_presence(prev)
    async with AsyncSessionLocal() as db:
        pres = SessionPresence(
            session_id=session_id, user_id=user_id, joined_at=datetime.now(UTC)
        )
        db.add(pres)
        await db.commit()
        presence_id = pres.id
    await _redis.set(_PRESENCE_KEY.format(sid=sid), presence_id, ex=_PRESENCE_TTL)


@sio.event
async def connect(sid: str, environ: dict, auth: dict | None = None) -> bool:
    """Accept only sockets carrying a valid session cookie."""
    user_id = resolve_user_id_from_environ(environ)
    if not user_id:
        return False  # rejects the connection
    await sio.save_session(sid, {"user_id": user_id})
    return True


async def authorize_join(
    db: AsyncSession, user: User | None, cs: ClassSession | None, user_id: str
) -> tuple[bool, bool]:
    """Decide whether a socket may enter a session's rooms.

    Returns (allowed, is_privileged). Instructors/admins/the host are always
    allowed and privileged. Everyone else must be enrolled in the session's
    course — otherwise they could listen to all live broadcasts (polls, quizzes,
    notices, leaderboard) without authorization.
    """
    is_privileged = bool(
        user
        and (
            user.role in (UserRole.INSTRUCTOR, UserRole.ADMIN)
            or (cs is not None and cs.host_id == user_id)
        )
    )
    if is_privileged:
        return True, True
    if user is None or cs is None:
        return False, False
    enrolled = await db.scalar(
        select(Enrollment).where(
            Enrollment.user_id == user_id,
            Enrollment.course_id == cs.course_id,
        )
    )
    return enrolled is not None, False


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
        allowed, is_privileged = await authorize_join(db, user, cs, user_id)
    if not allowed:
        return

    for room in compute_rooms(session_id, user_id, is_privileged=is_privileged):
        await sio.enter_room(sid, room)

    # Record attendance presence (server-observed; the free-plan signal).
    await _open_presence(sid, session_id, user_id)


@sio.event
async def caption_received(sid: str, data: dict) -> None:
    data = data or {}
    session_id = data.get("sessionId")
    text = data.get("text")
    if session_id and text:
        await buffer_caption(_redis, session_id, text, data.get("timestamp", 0))


@sio.event
async def raise_hand_up(sid: str, data: dict) -> None:
    """Student raises a hand — notify only the instructor room (ephemeral)."""
    session = await sio.get_session(sid)
    user_id = session.get("user_id")
    session_id = (data or {}).get("sessionId")
    if not user_id or not session_id:
        return
    await sio.emit(
        "raise_hand:up",
        {"userId": user_id, "name": (data or {}).get("name")},
        room=instructor_room(session_id),
    )


@sio.event
async def raise_hand_down(sid: str, data: dict) -> None:
    """Hand lowered (by the student, or the instructor calling on them)."""
    session = await sio.get_session(sid)
    user_id = session.get("user_id")
    data = data or {}
    session_id = data.get("sessionId")
    if not user_id or not session_id:
        return
    # An instructor can lower someone else's hand; default to the caller's.
    target = data.get("userId", user_id)
    await sio.emit("raise_hand:down", {"userId": target}, room=session_room(session_id))


@sio.event
async def disconnect(sid: str) -> None:
    # Close the attendance presence row opened for this socket.
    key = _PRESENCE_KEY.format(sid=sid)
    presence_id = await _redis.get(key)
    if presence_id:
        await _redis.delete(key)
        await _close_presence(presence_id)


def mount(fastapi_app) -> socketio.ASGIApp:
    """Wrap the FastAPI app so socket.io shares the same ASGI server."""
    return socketio.ASGIApp(sio, other_asgi_app=fastapi_app)
