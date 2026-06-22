"""Realtime backbone: socket cookie auth, room computation, caption buffer."""

import redis.asyncio as aioredis

from app.auth.tokens import create_access_token
from app.core.config import settings
from app.realtime.auth import resolve_user_id_from_environ
from app.realtime.captions import buffer_caption, caption_key, get_captions
from app.realtime.rooms import compute_rooms

# --- cookie auth ------------------------------------------------------------


def test_resolve_user_from_valid_cookie():
    token = create_access_token("user-123")
    environ = {"HTTP_COOKIE": f"{settings.COOKIE_NAME}={token}; other=x"}
    assert resolve_user_id_from_environ(environ) == "user-123"


def test_resolve_user_no_cookie():
    assert resolve_user_id_from_environ({}) is None


def test_resolve_user_invalid_token():
    environ = {"HTTP_COOKIE": f"{settings.COOKIE_NAME}=not-a-jwt"}
    assert resolve_user_id_from_environ(environ) is None


# --- rooms ------------------------------------------------------------------


def test_rooms_student():
    assert compute_rooms("s1", "u1", is_privileged=False) == [
        "session:s1",
        "session:s1:u1",
    ]


def test_rooms_instructor_gets_instructor_room():
    rooms = compute_rooms("s1", "u1", is_privileged=True)
    assert "session:s1:instructor" in rooms
    assert "session:s1" in rooms
    assert "session:s1:u1" in rooms


# --- caption buffer (real Redis) -------------------------------------------


async def test_caption_buffer_keeps_last_50():
    redis = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    await redis.delete(caption_key("buftest"))
    try:
        for i in range(60):
            await buffer_caption(redis, "buftest", f"line {i}", timestamp=i)
        captions = await get_captions(redis, "buftest")
        assert len(captions) == 50
        assert captions[0] == "line 10"  # oldest 10 trimmed
        assert captions[-1] == "line 59"
    finally:
        await redis.delete(caption_key("buftest"))
        await redis.aclose()


# --- join authorization (enrollment-gated broadcast access) -----------------


async def _mk_user(session, email, role):
    from app.auth.security import hash_password
    from app.models.user import User

    u = User(
        email=email,
        hashed_password=hash_password("passphrase-realtime"),
        display_name=email.split("@")[0],
        role=role,
    )
    session.add(u)
    await session.commit()
    return u


async def _mk_session(session, host, cid="c-rt"):
    from datetime import UTC, datetime

    from app.models.course import ClassSession, Course

    session.add(Course(id=cid, title="RT"))
    await session.flush()
    cs = ClassSession(
        course_id=cid,
        host_id=host.id,
        title="RT Session",
        scheduled_at=datetime.now(UTC),
        duration_mins=60,
    )
    session.add(cs)
    await session.commit()
    return cs


async def test_join_auth_denies_unenrolled_student(session):
    from app.models.user import UserRole
    from app.realtime.server import authorize_join

    host = await _mk_user(session, "host-rt@x.com", UserRole.INSTRUCTOR)
    outsider = await _mk_user(session, "outsider@x.com", UserRole.STUDENT)
    cs = await _mk_session(session, host)

    allowed, privileged = await authorize_join(session, outsider, cs, outsider.id)
    assert allowed is False
    assert privileged is False


async def test_join_auth_allows_enrolled_student(session):
    from app.models.course import Enrollment
    from app.models.user import UserRole
    from app.realtime.server import authorize_join

    host = await _mk_user(session, "host-rt@x.com", UserRole.INSTRUCTOR)
    student = await _mk_user(session, "enrolled@x.com", UserRole.STUDENT)
    cs = await _mk_session(session, host)
    session.add(Enrollment(user_id=student.id, course_id=cs.course_id))
    await session.commit()

    allowed, privileged = await authorize_join(session, student, cs, student.id)
    assert allowed is True
    assert privileged is False


async def test_join_auth_allows_privileged_without_enrollment(session):
    from app.models.user import UserRole
    from app.realtime.server import authorize_join

    host = await _mk_user(session, "host-rt@x.com", UserRole.INSTRUCTOR)
    cs = await _mk_session(session, host)
    # Instructor host, no enrollment row — still privileged.
    allowed, privileged = await authorize_join(session, host, cs, host.id)
    assert allowed is True
    assert privileged is True


# --- wiring -----------------------------------------------------------------


def test_socket_handlers_registered():
    from app.realtime.server import sio

    handlers = sio.handlers.get("/", {})
    assert "connect" in handlers
    assert "join_session" in handlers
    assert "caption_received" in handlers
    assert "raise_hand_up" in handlers
    assert "raise_hand_down" in handlers
