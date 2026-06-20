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


# --- wiring -----------------------------------------------------------------


def test_socket_handlers_registered():
    from app.realtime.server import sio

    handlers = sio.handlers.get("/", {})
    assert "connect" in handlers
    assert "join_session" in handlers
    assert "caption_received" in handlers
    assert "raise_hand_up" in handlers
    assert "raise_hand_down" in handlers
