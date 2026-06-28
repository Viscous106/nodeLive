"""Real Zoom meetings via Server-to-Server OAuth.

The seeded sessions carry placeholder Zoom numbers, so the SDK join fails with
"meeting number not found (3707)". This module creates an actual Zoom meeting on
demand and fetches the host's **ZAK** token, so an instructor can START a class
from inside nodeLive and students can join it.

Live HTTP is behind a module-level `_get`/`_post` so the join endpoint's wiring
is unit-tested by monkeypatching these functions; the real REST calls are ported
from Zoom's documented API and exercised only with real S2S creds.
"""

import httpx

from app.core.config import settings
from app.utils.zoom_auth import get_zoom_access_token

_API = "https://api.zoom.us/v2"


def is_configured() -> bool:
    """Auto-create needs S2S creds AND a real host user (S2S has no 'me')."""
    return bool(
        settings.ZOOM_S2S_ACCOUNT_ID
        and settings.ZOOM_S2S_CLIENT_ID
        and settings.ZOOM_S2S_CLIENT_SECRET
        and settings.ZOOM_HOST_EMAIL
    )


async def _get(path: str) -> httpx.Response:
    token = await get_zoom_access_token()
    async with httpx.AsyncClient(timeout=15) as client:
        return await client.get(
            f"{_API}{path}", headers={"Authorization": f"Bearer {token}"}
        )


async def _post(path: str, json: dict) -> httpx.Response:
    token = await get_zoom_access_token()
    async with httpx.AsyncClient(timeout=15) as client:
        return await client.post(
            f"{_API}{path}", headers={"Authorization": f"Bearer {token}"}, json=json
        )


async def get_meeting(meeting_id: str) -> dict | None:
    """Return the Zoom meeting object (carries `password`) or None if it 404s."""
    resp = await _get(f"/meetings/{meeting_id}")
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    return resp.json()


async def create_meeting(topic: str) -> dict:
    """Create a recurring-no-fixed-time meeting the host can start anytime."""
    body = {
        "topic": topic[:200] or "nodeLive Class",
        "type": 3,  # recurring, no fixed time → joinable/startable on demand
        "settings": {
            "join_before_host": False,
            "waiting_room": False,
            "approval_type": 2,  # no registration
        },
    }
    resp = await _post(f"/users/{settings.ZOOM_HOST_EMAIL}/meetings", body)
    resp.raise_for_status()
    return resp.json()


async def get_host_zak() -> str:
    """ZAK for the host user — required to START a meeting via the Web SDK."""
    resp = await _get(f"/users/{settings.ZOOM_HOST_EMAIL}/token?type=zak")
    resp.raise_for_status()
    return resp.json().get("token", "")


def s2s_configured() -> bool:
    """S2S OAuth alone (no ZOOM_HOST_EMAIL needed) — enough to read reports."""
    return bool(
        settings.ZOOM_S2S_ACCOUNT_ID
        and settings.ZOOM_S2S_CLIENT_ID
        and settings.ZOOM_S2S_CLIENT_SECRET
    )


async def get_past_instances(meeting_number: str) -> list[str]:
    """UUIDs of every past occurrence of a meeting number (oldest→newest).

    Lets attendance be reconciled straight from the Reports API even when the
    `meeting.started` webhook never created a Meeting row (webhook spine down).
    """
    resp = await _get(f"/past_meetings/{meeting_number}/instances")
    if resp.status_code == 404:
        return []
    resp.raise_for_status()
    data = resp.json()
    return [m["uuid"] for m in (data.get("meetings") or []) if m.get("uuid")]


async def ensure_meeting(current_id: str | None, topic: str) -> dict:
    """Get the existing Zoom meeting if `current_id` is real, else create one.

    Returns `{"id": <str meeting number>, "password": <str>}`. The caller persists
    `id` back onto the session (placeholder seed numbers get replaced here).
    """
    if current_id:
        existing = await get_meeting(current_id)
        if existing is not None:
            return {
                "id": str(existing["id"]),
                "password": existing.get("password", ""),
            }
    created = await create_meeting(topic)
    return {"id": str(created["id"]), "password": created.get("password", "")}
