"""Zoom Server-to-Server OAuth (account_credentials grant).

Used by the Reports API (attendance reconcile) and recording downloads. Caches
the token in-process until shortly before expiry. Ported from
`testing/lib/zoomAuth.js`.
"""

import base64
import time

import httpx

from app.core.config import settings

_TOKEN_URL = "https://zoom.us/oauth/token"
_cache: dict = {"token": None, "expires_at": 0.0}


async def get_zoom_access_token() -> str:
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
    _cache["token"] = data["access_token"]
    _cache["expires_at"] = now + data.get("expires_in", 3600) - 60  # refresh early
    return _cache["token"]


def reset_token_cache() -> None:
    """Test/util: clear the cached token."""
    _cache["token"] = None
    _cache["expires_at"] = 0.0
