"""Authoritative attendance reconciliation (Celery).

After a meeting ends, the Reports API is the source of truth. We pull the
participant report **by meeting UUID** (not the numeric id, which returns the
wrong instance for recurring meetings), union each identity's join/leave spans
so reconnects don't double-count, and **delete-then-insert** `attendance_final`
for that UUID — an idempotent recompute that also sidesteps the NULL-in-unique
upsert trap (Postgres treats NULL user_id/email as distinct).

The Reports-API + DB IO sits behind an injection seam (`get_token`, `http_get`,
`write`) so the reconcile wiring is tested offline; `reconcile_participants` is
the pure, fully-tested core. Ported from `testing/workers/reconcile.js`.
"""

import asyncio
import logging
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime

import httpx
from sqlalchemy import delete

from app.core.config import settings
from app.db.session import AsyncSessionLocal
from app.models.attendance import AttendanceFinal
from app.utils.attendance import encode_meeting_uuid, reconcile_participants
from app.utils.zoom_auth import get_zoom_access_token
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)

_API_BASE = "https://api.zoom.us/v2"


async def _default_http_get(url: str, token: str) -> dict:
    async with httpx.AsyncClient() as client:
        resp = await client.get(url, headers={"Authorization": f"Bearer {token}"})
        resp.raise_for_status()
        return resp.json()


async def _fetch_paged(
    base_path: str,
    enc: str,
    token: str,
    http_get: Callable[[str, str], Awaitable[dict]],
) -> list[dict]:
    participants: list[dict] = []
    next_page = ""
    while True:
        url = f"{_API_BASE}{base_path}/{enc}/participants?page_size=300"
        if next_page:
            url += f"&next_page_token={next_page}"
        data = await http_get(url, token)
        participants.extend(data.get("participants") or [])
        next_page = data.get("next_page_token") or ""
        if not next_page:
            break
    return participants


async def _fetch_all_participants(
    uuid: str,
    *,
    get_token: Callable[[], Awaitable[str]],
    http_get: Callable[[str, str], Awaitable[dict]],
) -> list[dict]:
    """Pull the participant list for a meeting instance.

    The Reports API (`/report/meetings`) has the richest data (it carries our
    `customer_key`) but needs the `report:read:*` scope AND a paid Zoom plan.
    When that call is rejected for scope/plan reasons, fall back to
    `/past_meetings` (the lighter `meeting:read:list_past_participants` scope
    family, available on more plans) — identity then matches on email.
    """
    token = await get_token()
    enc = encode_meeting_uuid(uuid)
    try:
        return await _fetch_paged("/report/meetings", enc, token, http_get)
    except httpx.HTTPStatusError as e:
        if e.response.status_code in (400, 401, 403):
            logger.warning(
                "reports API unavailable (%s) for %s; falling back to past_meetings",
                e.response.status_code,
                uuid,
            )
            return await _fetch_paged("/past_meetings", enc, token, http_get)
        raise


async def _write_finals(uuid: str, finals: list[dict]) -> None:
    async with AsyncSessionLocal() as db:
        # Authoritative recompute: replace this meeting's rows wholesale.
        await db.execute(
            delete(AttendanceFinal).where(AttendanceFinal.zoom_uuid == uuid)
        )
        now = datetime.now(UTC)
        for f in finals:
            db.add(
                AttendanceFinal(
                    zoom_uuid=uuid,
                    user_id=f["user_id"],
                    email=f["email"],
                    display_name=f["display_name"],
                    present_seconds=f["present_seconds"],
                    sessions=f["sessions"],
                    computed_at=now,
                )
            )
        await db.commit()


async def run_reconcile(
    uuid: str,
    *,
    get_token: Callable[[], Awaitable[str]] | None = None,
    http_get: Callable[[str, str], Awaitable[dict]] | None = None,
    write: Callable[[str, list[dict]], Awaitable[None]] | None = None,
) -> int:
    if not uuid:
        raise ValueError("reconcile: missing zoom_uuid")
    get_token = get_token or get_zoom_access_token
    http_get = http_get or _default_http_get
    write = write or _write_finals

    participants = await _fetch_all_participants(
        uuid, get_token=get_token, http_get=http_get
    )
    finals = reconcile_participants(participants)
    await write(uuid, finals)
    logger.info(
        "attendance reconcile %s: %d participants -> %d attendees",
        uuid,
        len(participants),
        len(finals),
    )
    return len(finals)


@celery_app.task(
    name="attendance.reconcile",
    autoretry_for=(Exception,),
    max_retries=5,
    retry_backoff=True,  # exponential: 1s, 2s, 4s, 8s, 16s
    retry_backoff_max=300,  # cap at 5 minutes
)
def reconcile_attendance(zoom_uuid: str) -> int:
    return asyncio.run(run_reconcile(zoom_uuid))


def schedule_reconcile(zoom_uuid: str) -> None:
    """Enqueue reconcile to run after Zoom finalizes the participant report."""
    reconcile_attendance.apply_async(
        args=[zoom_uuid], countdown=settings.ATTENDANCE_RECONCILE_DELAY_SECS
    )
