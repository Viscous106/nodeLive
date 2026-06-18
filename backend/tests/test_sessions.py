"""Session contract — GET/PATCH /api/sessions/:id (consumed by live-meeting).

This is the interface Dev B depends on: read a session's title/host/zoom id,
and flip its status to LIVE/ENDED.
"""

from datetime import UTC, datetime


async def _signup(client, email, role=None):
    """Create + authenticate a user; return their id. Optionally set role."""
    resp = await client.post(
        "/api/auth/signup",
        json={"email": email, "password": "passphrase here", "displayName": "U"},
    )
    return resp.json()["id"]


async def _seed_session(session, host_id, status="SCHEDULED"):
    from app.models.course import ClassSession, Course, SessionStatus

    session.add(Course(id="course-1", title="Databases"))
    await session.flush()
    session.add(
        ClassSession(
            id="session-1",
            course_id="course-1",
            host_id=host_id,
            title="Isolation Levels",
            scheduled_at=datetime(2026, 7, 1, 10, 0, tzinfo=UTC),
            duration_mins=90,
            zoom_meeting_id="8800011122",
            status=SessionStatus(status),
        )
    )
    await session.commit()


async def test_get_session_returns_contract_shape(client, session):
    host_id = await _signup(client, "host@example.com")
    await _seed_session(session, host_id)

    resp = await client.get("/api/sessions/session-1")

    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == "session-1"
    assert body["courseId"] == "course-1"
    assert body["hostId"] == host_id
    assert body["title"] == "Isolation Levels"
    assert body["durationMins"] == 90
    assert body["zoomMeetingId"] == "8800011122"
    assert body["status"] == "SCHEDULED"
    assert body["scheduledAt"].startswith("2026-07-01T10:00:00")


async def test_get_session_requires_auth(client, session):
    host_id = await _signup(client, "host@example.com")
    await _seed_session(session, host_id)
    client.cookies.clear()

    resp = await client.get("/api/sessions/session-1")
    assert resp.status_code == 401


async def test_get_unknown_session_is_404(client):
    await _signup(client, "someone@example.com")
    resp = await client.get("/api/sessions/does-not-exist")
    assert resp.status_code == 404


async def test_host_can_patch_status_to_live(client, session):
    host_id = await _signup(client, "host@example.com")
    await _seed_session(session, host_id)

    resp = await client.patch("/api/sessions/session-1", json={"status": "LIVE"})

    assert resp.status_code == 200
    assert resp.json()["status"] == "LIVE"


async def test_non_host_student_cannot_patch(client, session):
    host_id = await _signup(client, "host@example.com")
    await _seed_session(session, host_id)
    # switch to a different (student) user
    client.cookies.clear()
    await _signup(client, "student@example.com")

    resp = await client.patch("/api/sessions/session-1", json={"status": "ENDED"})
    assert resp.status_code == 403
