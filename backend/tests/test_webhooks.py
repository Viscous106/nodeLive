"""Zoom webhook HTTP path: raw-body HMAC verification, the url-validation
handshake, idempotent redelivery, and participant join/leave → attendance_sessions.
"""

import hashlib
import hmac
import json

import pytest
from sqlalchemy import select

from app.core.config import settings
from app.models.attendance import AttendanceSession, Meeting
from app.workers import attendance_tasks

SECRET = "test-webhook-secret"


@pytest.fixture
def scheduled(monkeypatch):
    """Stub the Celery reconcile scheduler and capture its calls."""
    calls: list[str] = []
    monkeypatch.setattr(settings, "ZOOM_WEBHOOK_SECRET_TOKEN", SECRET)
    monkeypatch.setattr(
        attendance_tasks, "schedule_reconcile", lambda uuid: calls.append(uuid)
    )
    return calls


def _body(event: dict) -> bytes:
    return json.dumps(event).encode()


def _signed_headers(body: bytes, ts: str = "1700000000") -> dict:
    sig = (
        "v0="
        + hmac.new(
            SECRET.encode(), f"v0:{ts}:{body.decode()}".encode(), hashlib.sha256
        ).hexdigest()
    )
    return {
        "content-type": "application/json",
        "x-zm-request-timestamp": ts,
        "x-zm-signature": sig,
    }


async def _post(client, event, *, sign=True, headers=None):
    body = _body(event)
    hdrs = (
        _signed_headers(body)
        if sign
        else (headers or {"content-type": "application/json"})
    )
    return await client.post("/api/webhooks/zoom", content=body, headers=hdrs)


# --- handshake + signature --------------------------------------------------


async def test_url_validation_handshake(client, scheduled):
    event = {"event": "endpoint.url_validation", "payload": {"plainToken": "abc123"}}
    # No signature on the handshake — it must still succeed.
    r = await _post(client, event, sign=False)
    assert r.status_code == 200
    body = r.json()
    assert body["plainToken"] == "abc123"
    expected = hmac.new(SECRET.encode(), b"abc123", hashlib.sha256).hexdigest()
    assert body["encryptedToken"] == expected


async def test_invalid_signature_rejected(client, scheduled):
    event = {"event": "meeting.started", "payload": {"object": {"uuid": "U1"}}}
    r = await _post(
        client,
        event,
        sign=False,
        headers={
            "content-type": "application/json",
            "x-zm-request-timestamp": "1700000000",
            "x-zm-signature": "v0=deadbeef",
        },
    )
    assert r.status_code == 401


async def test_valid_signature_creates_meeting(client, session, scheduled):
    event = {
        "event": "meeting.started",
        "event_ts": 1,
        "payload": {
            "object": {
                "uuid": "U1",
                "id": "880",
                "topic": "DB",
                "start_time": "2026-06-20T10:00:00Z",
            }
        },
    }
    r = await _post(client, event)
    assert r.status_code == 200 and r.json()["status"] == "ok"
    m = await session.scalar(select(Meeting).where(Meeting.zoom_uuid == "U1"))
    assert m is not None and m.zoom_meeting_id == "880" and m.started_at is not None


# --- idempotency ------------------------------------------------------------


async def test_duplicate_event_ignored(client, session, scheduled):
    event = {
        "event": "meeting.participant_joined",
        "event_ts": 5,
        "payload": {
            "object": {
                "uuid": "U1",
                "participant": {
                    "participant_uuid": "P1",
                    "user_name": "A",
                    "join_time": "2026-06-20T10:00:00Z",
                },
            }
        },
    }
    r1 = await _post(client, event)
    r2 = await _post(client, event)
    assert r1.json()["status"] == "ok"
    assert r2.json()["status"] == "duplicate-ignored"
    rows = list(
        await session.scalars(
            select(AttendanceSession).where(AttendanceSession.zoom_uuid == "U1")
        )
    )
    assert len(rows) == 1  # not double-recorded


# --- participant join / leave ----------------------------------------------


async def test_participant_join_then_leave(client, session, scheduled):
    join = {
        "event": "meeting.participant_joined",
        "event_ts": 10,
        "payload": {
            "object": {
                "uuid": "U1",
                "participant": {
                    "participant_uuid": "P1",
                    "customer_key": "user-1",
                    "email": "a@x.com",
                    "user_name": "A",
                    "join_time": "2026-06-20T10:00:00Z",
                },
            }
        },
    }
    leave = {
        "event": "meeting.participant_left",
        "event_ts": 11,
        "payload": {
            "object": {
                "uuid": "U1",
                "participant": {
                    "participant_uuid": "P1",
                    "leave_time": "2026-06-20T10:30:00Z",
                },
            }
        },
    }
    await _post(client, join)
    await _post(client, leave)

    row = await session.scalar(
        select(AttendanceSession).where(AttendanceSession.zoom_participant_uuid == "P1")
    )
    assert row.user_id == "user-1"
    assert row.email == "a@x.com"
    assert row.joined_at is not None
    assert row.left_at is not None  # leave matched the join row


async def test_meeting_ended_schedules_reconcile(client, session, scheduled):
    started = {
        "event": "meeting.started",
        "event_ts": 1,
        "payload": {"object": {"uuid": "U9", "id": "881"}},
    }
    ended = {
        "event": "meeting.ended",
        "event_ts": 2,
        "payload": {"object": {"uuid": "U9", "end_time": "2026-06-20T11:00:00Z"}},
    }
    await _post(client, started)
    await _post(client, ended)
    assert scheduled == ["U9"]
    m = await session.scalar(select(Meeting).where(Meeting.zoom_uuid == "U9"))
    assert m.ended_at is not None


async def test_recording_completed_marks_pending_and_schedules(
    client, session, scheduled, monkeypatch
):
    from app.workers import recording_tasks

    captured = {}

    def fake_schedule(uuid, token, files):
        captured["args"] = (uuid, token, files)

    monkeypatch.setattr(recording_tasks, "schedule_ingest", fake_schedule)

    event = {
        "event": "recording.completed",
        "event_ts": 7,
        "download_token": "dl-tok",
        "payload": {
            "object": {
                "uuid": "rec-uuid-1",
                "id": "82912345678",
                "topic": "DB Indexing",
                "recording_files": [
                    {
                        "file_type": "MP4",
                        "recording_type": "shared_screen_with_speaker_view",
                        "download_url": "https://zoom.us/rec/x.mp4",
                    }
                ],
            }
        },
    }
    resp = await _post(client, event)
    assert resp.status_code == 200

    m = await session.scalar(select(Meeting).where(Meeting.zoom_uuid == "rec-uuid-1"))
    assert m is not None
    assert m.recording_status == "pending"
    assert captured["args"][0] == "rec-uuid-1"
    assert captured["args"][1] == "dl-tok"
    assert captured["args"][2][0]["download_url"] == "https://zoom.us/rec/x.mp4"
