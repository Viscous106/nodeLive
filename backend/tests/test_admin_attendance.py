"""Admin attendance endpoint: GET /api/admin/sessions/:id/attendance."""

from datetime import UTC, datetime, timedelta

import pytest

from app.auth.security import hash_password
from app.models.attendance import AttendanceFinal, Meeting
from app.models.course import ClassSession, Course, Enrollment
from app.models.user import User, UserRole
from app.services.roles import assign_role

_PW = "passphrase-9876"


async def _user(session, email, role=UserRole.STUDENT):
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


async def _course(session, cid="c-att"):
    c = Course(id=cid, title="Attendance Course")
    session.add(c)
    await session.commit()
    return c


async def _session(session, course, host, zoom_id="12345678"):
    cs = ClassSession(
        course_id=course.id,
        host_id=host.id,
        title="Test Session",
        scheduled_at=datetime.now(UTC) - timedelta(hours=2),
        duration_mins=60,
        zoom_meeting_id=zoom_id,
    )
    session.add(cs)
    await session.commit()
    return cs


async def _enroll(session, user, course):
    enr = Enrollment(user_id=user.id, course_id=course.id)
    session.add(enr)
    await session.commit()
    return enr


async def _meeting(session, zoom_id, zoom_uuid="uuid-001"):
    m = Meeting(
        zoom_uuid=zoom_uuid,
        zoom_meeting_id=zoom_id,
        started_at=datetime.now(UTC) - timedelta(hours=2),
        ended_at=datetime.now(UTC) - timedelta(hours=1),
    )
    session.add(m)
    await session.commit()
    return m


async def _attendance(session, zoom_uuid, user_id, seconds):
    af = AttendanceFinal(
        zoom_uuid=zoom_uuid,
        user_id=user_id,
        present_seconds=seconds,
        sessions=[],
    )
    session.add(af)
    await session.commit()
    return af


async def _login(client, email):
    client.cookies.clear()
    r = await client.post("/api/auth/login", json={"email": email, "password": _PW})
    assert r.status_code == 200, r.text


@pytest.mark.asyncio
async def test_attendance_returns_enrolled_users(client, session):
    admin = await _user(session, "admin@x.com", UserRole.ADMIN)
    student = await _user(session, "student@x.com", UserRole.STUDENT)
    course = await _course(session)
    cs = await _session(session, course, admin, zoom_id="99001122")
    await _enroll(session, student, course)
    await _login(client, "admin@x.com")

    r = await client.get(f"/api/admin/sessions/{cs.id}/attendance")
    assert r.status_code == 200
    data = r.json()
    user_ids = [d["userId"] for d in data]
    assert student.id in user_ids


@pytest.mark.asyncio
async def test_attendance_marks_attended_when_final_record_exists(client, session):
    admin = await _user(session, "admin@x.com", UserRole.ADMIN)
    student = await _user(session, "student@x.com", UserRole.STUDENT)
    course = await _course(session)
    cs = await _session(session, course, admin, zoom_id="77001122")
    await _enroll(session, student, course)
    mtg = await _meeting(session, zoom_id="77001122", zoom_uuid="uuid-s1")
    await _attendance(session, mtg.zoom_uuid, student.id, seconds=1800)
    await _login(client, "admin@x.com")

    r = await client.get(f"/api/admin/sessions/{cs.id}/attendance")
    assert r.status_code == 200
    row = next(d for d in r.json() if d["userId"] == student.id)
    assert row["attended"] is True
    assert row["presentSeconds"] == 1800


@pytest.mark.asyncio
async def test_attendance_no_data_when_no_meeting_record(client, session):
    admin = await _user(session, "admin@x.com", UserRole.ADMIN)
    student = await _user(session, "student@x.com", UserRole.STUDENT)
    course = await _course(session)
    cs = await _session(session, course, admin, zoom_id="55001122")
    await _enroll(session, student, course)
    await _login(client, "admin@x.com")

    r = await client.get(f"/api/admin/sessions/{cs.id}/attendance")
    assert r.status_code == 200
    row = next(d for d in r.json() if d["userId"] == student.id)
    assert row["attended"] is False
    assert row["presentSeconds"] == 0


@pytest.mark.asyncio
async def test_attendance_404_for_unknown_session(client, session):
    await _user(session, "admin@x.com", UserRole.ADMIN)
    await _login(client, "admin@x.com")

    r = await client.get("/api/admin/sessions/nonexistent-id/attendance")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_attendance_403_for_non_admin(client, session):
    instructor = await _user(session, "inst@x.com", UserRole.INSTRUCTOR)
    course = await _course(session)
    cs = await _session(session, course, instructor)
    await _login(client, "inst@x.com")

    r = await client.get(f"/api/admin/sessions/{cs.id}/attendance")
    assert r.status_code == 403
