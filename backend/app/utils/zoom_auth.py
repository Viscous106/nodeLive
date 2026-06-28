"""Zoom Server-to-Server OAuth (account_credentials grant).

Used by the Reports API (attendance reconcile) and recording downloads. The token
is cached in Redis (shared across the web process and Celery workers, survives a
restart) with a fast in-process fallback. A sync Redis client is used on purpose:
the reconcile worker runs each task in a fresh `asyncio.run` loop, which an
async/module-level Redis client could not be safely shared across. Ported from
`testing/lib/zoomAuth.js`.
"""

import base64
import contextlib
import logging
import time

import httpx
import redis

from app.core.config import settings

logger = logging.getLogger(__name__)

_TOKEN_URL = "https://zoom.us/oauth/token"
_CACHE_KEY = "nodelive:zoom:access_token"
# In-process fallback used when Redis is unreachable, so a Redis blip can't break
# Zoom calls (it just means each process may fetch its own token).
_cache: dict = {"token": None, "expires_at": 0.0}

try:
    _redis: redis.Redis | None = redis.from_url(
        settings.REDIS_URL, decode_responses=True
    )
except Exception:  # pragma: no cover - malformed URL etc.
    _redis = None


def _redis_get() -> str | None:
    if _redis is None:
        return None
    try:
        return _redis.get(_CACHE_KEY)
    except Exception:
        logger.warning("zoom token: Redis GET failed; using in-process cache")
        return None


def _redis_set(token: str, ttl: int) -> None:
    if _redis is None or ttl <= 0:
        return
    try:
        _redis.setex(_CACHE_KEY, ttl, token)
    except Exception:
        logger.warning("zoom token: Redis SETEX failed; caching in-process only")


async def get_zoom_access_token() -> str:
    cached = _redis_get()
    if cached:
        return cached

    now = time.time()
    if _cache["token"] and now < _cache["expires_at"]:
        return _cache["token"]

    account_id = settings.ZOOM_S2S_ACCOUNT_ID
    client_id = settings.ZOOM_S2S_CLIENT_ID
    client_secret = settings.ZOOM_S2S_CLIENT_SECRET
    if not (account_id and client_id and client_secret):
        raise RuntimeError(
            "Missing ZOOM_S2S_ACCOUNT_ID / CLIENT_ID / CLIENT_SECRET in env"
        )

    basic = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            _TOKEN_URL,
            params={"grant_type": "account_credentials", "account_id": account_id},
            headers={"Authorization": f"Basic {basic}"},
        )
    resp.raise_for_status()
    data = resp.json()
    token = data["access_token"]
    ttl = data.get("expires_in", 3600) - 60  # refresh early
    _cache["token"] = token
    _cache["expires_at"] = now + ttl
    _redis_set(token, ttl)
    return token


def reset_token_cache() -> None:
    """Test/util: clear the cached token (both Redis and in-process)."""
    _cache["token"] = None
    _cache["expires_at"] = 0.0
    if _redis is not None:
        with contextlib.suppress(Exception):
            _redis.delete(_CACHE_KEY)
