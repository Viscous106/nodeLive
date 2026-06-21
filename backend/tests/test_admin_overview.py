"""Admin overview endpoint: GET /api/admin/overview."""

from datetime import UTC, datetime, timedelta

import pytest

from app.auth.security import hash_password
from app.models.course import ClassSession, Course, Enrollment, SessionStatus
from app.models.user import User, UserRole
from app.services.roles import assign_role

_PW = "pass-overview-99"


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


async def _login(client, email):
    client.cookies.clear()
    r = await client.post("/api/auth/login", json={"email": email, "password": _PW})
    assert r.status_code == 200, r.text


async def _course(session, cid="c1", title="DB"):
    c = Course(id=cid, title=title)
    session.add(c)
    await session.commit()
    return c


async def _session(
    session, course, host, status=SessionStatus.SCHEDULED, offset_days=1
):
    cs = ClassSession(
        course_id=course.id,
        host_id=host.id,
        title=f"Session {offset_days}",
        scheduled_at=datetime.now(UTC) + timedelta(days=offset_days),
        duration_mins=60,
        status=status,
    )
    session.add(cs)
    await session.commit()
    return cs


@pytest.mark.asyncio
async def test_overview_counts(client, session):
    admin = await _user(session, "admin@x.com", UserRole.ADMIN)
    student = await _user(session, "stu@x.com", UserRole.STUDENT)
    await _user(session, "inst@x.com", UserRole.INSTRUCTOR)
    course = await _course(session)
    await _session(session, course, admin, SessionStatus.SCHEDULED, offset_days=1)
    await _session(session, course, admin, SessionStatus.ENDED, offset_days=-1)
    session.add(Enrollment(user_id=student.id, course_id=course.id))
    await session.commit()
    await _login(client, "admin@x.com")

    r = await client.get("/api/admin/overview")
    assert r.status_code == 200
    data = r.json()
    assert data["totalMembers"] == 3
    assert data["students"] == 1
    assert data["instructors"] == 1
    assert data["admins"] == 1
    assert data["totalCourses"] == 1
    assert data["totalEnrollments"] == 1
    assert data["sessions"]["scheduled"] == 1
    assert data["sessions"]["ended"] == 1
    assert data["sessions"]["live"] == 0


@pytest.mark.asyncio
async def test_overview_upcoming_sorted_ascending(client, session):
    admin = await _user(session, "admin@x.com", UserRole.ADMIN)
    course = await _course(session)
    cs1 = await _session(session, course, admin, offset_days=3)
    cs2 = await _session(session, course, admin, offset_days=1)
    await _login(client, "admin@x.com")

    r = await client.get("/api/admin/overview")
    assert r.status_code == 200
    ids = [u["id"] for u in r.json()["upcoming"]]
    assert ids.index(cs2.id) < ids.index(cs1.id)


@pytest.mark.asyncio
async def test_overview_403_for_non_admin(client, session):
    await _user(session, "inst@x.com", UserRole.INSTRUCTOR)
    await _login(client, "inst@x.com")

    r = await client.get("/api/admin/overview")
    assert r.status_code == 403
