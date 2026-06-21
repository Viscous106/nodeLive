"""Tests for platform milestone endpoints.

Covers:
- GET /admin/overview   — counts + upcoming sessions
- GET /admin/sessions/{id}/attendance — per-user attendance rows
- PATCH /api/auth/me   — profile update
"""

from datetime import UTC, datetime, timedelta

import pytest

from app.auth.security import hash_password
from app.models.course import ClassSession, Course, Enrollment, SessionStatus
from app.models.user import User, UserRole
from app.services.roles import assign_role

_PW = "test-passphrase-99"


async def _make_user(session, email, role=UserRole.STUDENT):
    u = User(
        email=email,
        hashed_password=hash_password(_PW),
        display_name=email.split("@")[0],
        role=role,
    )
    session.add(u)
    await session.commit()
    await assign_role(session, u, role)
    await session.commit()
    return u


async def _make_course(session, title="Test Course"):
    c = Course(title=title)
    session.add(c)
    await session.commit()
    return c


async def _login(client, email):
    client.cookies.clear()
    r = await client.post("/api/auth/login", json={"email": email, "password": _PW})
    assert r.status_code == 200, r.text


# ---------------------------------------------------------------------------
# GET /admin/overview
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_admin_overview_counts(client, session):
    admin = await _make_user(session, "admin-ov@x.com", UserRole.ADMIN)
    student = await _make_user(session, "stu-ov@x.com", UserRole.STUDENT)
    course = await _make_course(session, "Overview Course")

    enr = Enrollment(user_id=student.id, course_id=course.id)
    session.add(enr)

    # One upcoming scheduled session.
    cs = ClassSession(
        course_id=course.id,
        host_id=admin.id,
        title="Upcoming Session",
        scheduled_at=datetime.now(UTC) + timedelta(days=1),
        duration_mins=60,
        status=SessionStatus.SCHEDULED,
    )
    session.add(cs)
    await session.commit()

    await _login(client, "admin-ov@x.com")
    r = await client.get("/api/admin/overview")
    assert r.status_code == 200, r.text
    body = r.json()

    # 2 users were created (admin + student).
    assert body["members"] >= 2
    assert body["courses"] >= 1
    assert body["enrollments"] >= 1
    assert "sessionsByStatus" in body
    assert "upcomingSessions" in body
    # The upcoming session should appear.
    upcoming_ids = [s["id"] for s in body["upcomingSessions"]]
    assert cs.id in upcoming_ids


@pytest.mark.asyncio
async def test_admin_overview_requires_admin(client, session):
    await _make_user(session, "stu-ov2@x.com", UserRole.STUDENT)
    await _login(client, "stu-ov2@x.com")
    r = await client.get("/api/admin/overview")
    assert r.status_code == 403


# ---------------------------------------------------------------------------
# GET /admin/sessions/{session_id}/attendance
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_admin_attendance_no_zoom(client, session):
    """Session without zoom_meeting_id → all enrolled users present 0 s."""
    admin = await _make_user(session, "admin-att@x.com", UserRole.ADMIN)
    student = await _make_user(session, "stu-att@x.com", UserRole.STUDENT)
    course = await _make_course(session, "Attendance Course")

    enr = Enrollment(user_id=student.id, course_id=course.id)
    session.add(enr)

    cs = ClassSession(
        course_id=course.id,
        host_id=admin.id,
        title="No Zoom Session",
        scheduled_at=datetime.now(UTC) + timedelta(days=2),
        duration_mins=60,
        status=SessionStatus.SCHEDULED,
        # zoom_meeting_id intentionally omitted
    )
    session.add(cs)
    await session.commit()

    await _login(client, "admin-att@x.com")
    r = await client.get(f"/api/admin/sessions/{cs.id}/attendance")
    assert r.status_code == 200, r.text
    body = r.json()

    assert body["sessionId"] == cs.id
    assert body["sessionTitle"] == "No Zoom Session"
    assert body["durationMins"] == 60
    # The enrolled student row should appear with 0 present seconds.
    rows = body["rows"]
    assert len(rows) >= 1
    student_rows = [row for row in rows if row["userId"] == student.id]
    assert len(student_rows) == 1
    assert student_rows[0]["presentSeconds"] == 0
    assert student_rows[0]["attended"] is False


@pytest.mark.asyncio
async def test_admin_attendance_unknown_session_404(client, session):
    await _make_user(session, "admin-att2@x.com", UserRole.ADMIN)
    await _login(client, "admin-att2@x.com")
    r = await client.get("/api/admin/sessions/does-not-exist/attendance")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_admin_attendance_requires_admin(client, session):
    admin = await _make_user(session, "admin-att3@x.com", UserRole.ADMIN)
    await _make_user(session, "stu-att3@x.com", UserRole.STUDENT)
    course = await _make_course(session, "Att Course 3")
    cs = ClassSession(
        course_id=course.id,
        host_id=admin.id,
        title="Session",
        scheduled_at=datetime.now(UTC) + timedelta(days=1),
        duration_mins=60,
        status=SessionStatus.SCHEDULED,
    )
    session.add(cs)
    await session.commit()

    await _login(client, "stu-att3@x.com")
    r = await client.get(f"/api/admin/sessions/{cs.id}/attendance")
    assert r.status_code == 403


# ---------------------------------------------------------------------------
# PATCH /api/auth/me
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_profile_update_name(client, session):
    await _make_user(session, "user-patch@x.com", UserRole.STUDENT)
    await _login(client, "user-patch@x.com")

    r = await client.patch("/api/auth/me", json={"displayName": "New Display Name"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["displayName"] == "New Display Name"
    assert body["email"] == "user-patch@x.com"

    # Persist check — GET /me should reflect the new name.
    me = await client.get("/api/auth/me")
    assert me.json()["displayName"] == "New Display Name"


@pytest.mark.asyncio
async def test_profile_update_blank_name_422(client, session):
    await _make_user(session, "user-blank@x.com", UserRole.STUDENT)
    await _login(client, "user-blank@x.com")

    r = await client.patch("/api/auth/me", json={"displayName": "   "})
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_profile_update_requires_auth(client, session):
    client.cookies.clear()
    r = await client.patch("/api/auth/me", json={"displayName": "Should Fail"})
    assert r.status_code == 401
