"""Zoom webhook ingestion — the durable attendance spine (ported from
`testing/routes/webhooks.js`).

Order matters and mirrors the reference:
  1. read the **raw bytes** (the HMAC is over exactly what Zoom sent — parsing
     to JSON first would change them);
  2. answer the `endpoint.url_validation` handshake **before** verifying (that
     request carries no signature);
  3. verify the `v0` HMAC over `v0:{ts}:{raw}` with a constant-time compare;
  4. claim the event in its own commit (idempotency — Zoom redelivers) so a
     later handler error can't roll the claim back;
  5. handle, swallowing errors and still acking 200 — the Reports-API reconcile
     is the source of truth, so ingestion is best-effort.
"""

import hashlib
import hmac
import json
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import get_db
from app.models.attendance import AttendanceSession, Meeting, WebhookEvent
from app.utils.attendance import build_event_id, parse_zoom_time
from app.workers import attendance_tasks, recording_tasks

router = APIRouter(tags=["webhooks"])


def _hmac(message: str) -> str:
    return hmac.new(
        settings.ZOOM_WEBHOOK_SECRET_TOKEN.encode(), message.encode(), hashlib.sha256
    ).hexdigest()


def _dt(secs: float | None) -> datetime | None:
    return datetime.fromtimestamp(secs, UTC) if secs is not None else None


@router.post("/webhooks/zoom")
async def zoom_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    raw = (await request.body()).decode("utf-8", "replace")
    try:
        event = json.loads(raw or "{}")
    except json.JSONDecodeError:
        return JSONResponse({"error": "invalid JSON"}, status_code=400)

    # 1) URL-validation handshake — echo HMAC of plainToken (no signature header).
    if event.get("event") == "endpoint.url_validation":
        plain = (event.get("payload") or {}).get("plainToken", "")
        return JSONResponse({"plainToken": plain, "encryptedToken": _hmac(plain)})

    # 2) Verify the v0 signature over the raw body.
    ts = request.headers.get("x-zm-request-timestamp", "")
    signature = request.headers.get("x-zm-signature", "")
    expected = "v0=" + _hmac(f"v0:{ts}:{raw}")
    if not signature or not hmac.compare_digest(expected, signature):
        return JSONResponse({"error": "invalid signature"}, status_code=401)

    # 3) Idempotency claim, committed on its own so a handler error can't un-claim.
    db.add(WebhookEvent(event_id=build_event_id(event)))
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        return JSONResponse({"status": "duplicate-ignored"})

    # 4) Handle. Best-effort: swallow errors and still ack (reconcile is truth).
    try:
        await _handle_event(db, event)
    except Exception:
        await db.rollback()
    return JSONResponse({"status": "ok"})


async def _handle_event(db: AsyncSession, event: dict) -> None:
    name = event.get("event", "")
    obj = (event.get("payload") or {}).get("object") or {}
    zoom_uuid = obj.get("uuid")
    if not zoom_uuid and name.startswith("meeting."):
        return

    if name == "meeting.started":
        await _upsert_meeting(
            db, zoom_uuid, obj, started=parse_zoom_time(obj.get("start_time"))
        )
    elif name == "meeting.participant_joined":
        await _upsert_meeting(db, zoom_uuid, obj)
        await _record_join(db, zoom_uuid, obj.get("participant") or {})
    elif name == "meeting.participant_left":
        await _record_leave(db, zoom_uuid, obj.get("participant") or {})
    elif name == "meeting.ended":
        await _mark_ended(db, zoom_uuid, parse_zoom_time(obj.get("end_time")))
        attendance_tasks.schedule_reconcile(zoom_uuid)
    elif name == "recording.completed":
        await _upsert_meeting(db, zoom_uuid, obj)
        meeting = await db.scalar(select(Meeting).where(Meeting.zoom_uuid == zoom_uuid))
        if meeting is not None:
            meeting.recording_status = "pending"
        download_token = event.get("download_token") or (
            (event.get("payload") or {}).get("download_token")
        )
        recording_files = obj.get("recording_files") or []
        recording_tasks.schedule_ingest(zoom_uuid, download_token, recording_files)

    await db.commit()


async def _upsert_meeting(
    db: AsyncSession, zoom_uuid: str, obj: dict, started: float | None = None
) -> None:
    meeting = await db.scalar(select(Meeting).where(Meeting.zoom_uuid == zoom_uuid))
    if meeting is None:
        meeting = Meeting(zoom_uuid=zoom_uuid)
        db.add(meeting)
    if obj.get("id"):
        meeting.zoom_meeting_id = str(obj["id"])
    if obj.get("topic"):
        meeting.topic = obj["topic"]
    if obj.get("host_id"):
        meeting.host_id = obj["host_id"]
    if started is not None:
        meeting.started_at = _dt(started)


def _participant_uuid(p: dict, time_key: str) -> str:
    return (
        p.get("participant_uuid")
        or p.get("user_id")
        or f"{p.get('user_name')}-{p.get(time_key)}"
    )


async def _record_join(db: AsyncSession, zoom_uuid: str, p: dict) -> None:
    puid = _participant_uuid(p, "join_time")
    existing = await db.scalar(
        select(AttendanceSession).where(
            AttendanceSession.zoom_uuid == zoom_uuid,
            AttendanceSession.zoom_participant_uuid == puid,
        )
    )
    if existing is not None:
        return  # redelivery / already recorded
    db.add(
        AttendanceSession(
            zoom_uuid=zoom_uuid,
            zoom_participant_uuid=puid,
            user_id=p.get("customer_key"),
            email=p.get("email"),
            display_name=p.get("user_name"),
            joined_at=_dt(parse_zoom_time(p.get("join_time"))),
        )
    )


async def _record_leave(db: AsyncSession, zoom_uuid: str, p: dict) -> None:
    puid = _participant_uuid(p, "leave_time")
    row = await db.scalar(
        select(AttendanceSession).where(
            AttendanceSession.zoom_uuid == zoom_uuid,
            AttendanceSession.zoom_participant_uuid == puid,
        )
    )
    if row is not None:
        row.left_at = _dt(parse_zoom_time(p.get("leave_time")))


async def _mark_ended(db: AsyncSession, zoom_uuid: str, ended: float | None) -> None:
    meeting = await db.scalar(select(Meeting).where(Meeting.zoom_uuid == zoom_uuid))
    if meeting is not None:
        meeting.ended_at = _dt(ended)
