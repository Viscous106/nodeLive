"""POST /api/sessions/:id/join — Zoom SDK credentials for the live meeting."""

import base64
import json
from datetime import UTC, datetime

from app.auth.security import hash_password

_PW = "passphrase-1234"


def _payload(signature: str) -> dict:
    part = signature.split(".")[1]
    pad = "=" * (-len(part) % 4)
    return json.loads(base64.urlsafe_b64decode(part + pad))


async def _user(session, email, role):
    from app.models.user import User, UserRole

    u = User(
        email=email,
        hashed_password=hash_password(_PW),
        display_name=email.split("@")[0],
        role=UserRole(role),
    )
    session.add(u)
    await session.commit()
    return u.id


async def _login(client, email):
    client.cookies.clear()
    await client.post("/api/auth/login", json={"email": email, "password": _PW})


async def _session_row(session, host_id, *, zoom="88012345", sid="s1", cid="c1"):
    from app.models.course import ClassSession, Course, SessionStatus

    session.add(Course(id=cid, title="DB"))
    await session.flush()
    session.add(
        ClassSession(
            id=sid,
            course_id=cid,
            host_id=host_id,
            title="Live",
            scheduled_at=datetime(2026, 7, 1, 10, 0, tzinfo=UTC),
            duration_mins=60,
            zoom_meeting_id=zoom,
            status=SessionStatus.LIVE,
        )
    )
    await session.commit()


async def _enroll(session, user_id, cid="c1"):
    from app.models.course import Enrollment

    session.add(Enrollment(user_id=user_id, course_id=cid))
    await session.commit()


async def test_enrolled_student_join_returns_signature(client, session):
    host = await _user(session, "prof@example.com", "INSTRUCTOR")
    await _session_row(session, host)
    sid = await _user(session, "stu@example.com", "STUDENT")
    await _enroll(session, sid)
    await _login(client, "stu@example.com")

    resp = await client.post("/api/sessions/s1/join")
    assert resp.status_code == 200
    body = resp.json()
    assert "sdkKey" in body
    assert body["zoomMeetingId"] == "88012345"
    assert body["signature"].count(".") == 2
    payload = _payload(body["signature"])
    assert payload["mn"] == "88012345"
    assert payload["role"] == 0  # attendee


async def test_host_gets_host_role(client, session):
    host = await _user(session, "prof@example.com", "INSTRUCTOR")
    await _session_row(session, host)
    await _login(client, "prof@example.com")

    resp = await client.post("/api/sessions/s1/join")
    assert resp.status_code == 200
    assert _payload(resp.json()["signature"])["role"] == 1  # host


async def test_non_enrolled_student_forbidden(client, session):
    host = await _user(session, "prof@example.com", "INSTRUCTOR")
    await _session_row(session, host)
    await _user(session, "stu@example.com", "STUDENT")
    await _login(client, "stu@example.com")

    resp = await client.post("/api/sessions/s1/join")
    assert resp.status_code == 403


async def test_session_without_zoom_meeting_is_conflict(client, session):
    host = await _user(session, "prof@example.com", "INSTRUCTOR")
    await _session_row(session, host, zoom=None, sid="s2")
    await _login(client, "prof@example.com")

    resp = await client.post("/api/sessions/s2/join")
    assert resp.status_code == 409


async def test_join_requires_auth(client, session):
    host = await _user(session, "prof@example.com", "INSTRUCTOR")
    await _session_row(session, host)
    client.cookies.clear()

    resp = await client.post("/api/sessions/s1/join")
    assert resp.status_code == 401


async def test_join_unknown_session_404(client, session):
    await _user(session, "stu@example.com", "STUDENT")
    await _login(client, "stu@example.com")

    resp = await client.post("/api/sessions/nope/join")
    assert resp.status_code == 404
