"""Session lifecycle production fixes:

- POST /api/admin/sessions/{id}/end — manual end fallback (P0 Fix 2)
- the stale-LIVE-session janitor (P1 Fix 6)
- GET /api/sessions?status=past excludes still-LIVE sessions (P3 Fix 12)
"""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.auth.security import hash_password
from app.models.attendance import Meeting
from app.models.course import ClassSession, Course, Enrollment, SessionStatus
from app.models.user import User, UserRole
from app.services.roles import assign_role
from app.workers import attendance_tasks, session_tasks

_PW = "passphrase-lifecycle"


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


async def _course(session, cid="c-life", title="Lifecycle"):
    c = Course(id=cid, title=title)
    session.add(c)
    await session.commit()
    return c


async def _session(session, course, host, *, status, scheduled_at, zoom_id=None):
    cs = ClassSession(
        course_id=course.id,
        host_id=host.id,
        title=f"Session {status.value}",
        scheduled_at=scheduled_at,
        duration_mins=60,
        zoom_meeting_id=zoom_id,
        status=status,
    )
    session.add(cs)
    await session.commit()
    return cs


async def _login(client, email):
    client.cookies.clear()
    r = await client.post("/api/auth/login", json={"email": email, "password": _PW})
    assert r.status_code == 200, r.text


# --- POST /admin/sessions/{id}/end -------------------------------------------


@pytest.mark.asyncio
async def test_end_live_session(client, session):
    admin = await _user(session, "admin@x.com", UserRole.ADMIN)
    course = await _course(session)
    cs = await _session(
        session,
        course,
        admin,
        status=SessionStatus.LIVE,
        scheduled_at=datetime.now(UTC) - timedelta(minutes=30),
    )
    await _login(client, "admin@x.com")

    r = await client.post(f"/api/admin/sessions/{cs.id}/end")
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "ENDED"
    await session.refresh(cs)
    assert cs.status == SessionStatus.ENDED
    assert cs.ended_at is not None


@pytest.mark.asyncio
async def test_end_scheduled_session_allowed(client, session):
    admin = await _user(session, "admin@x.com", UserRole.ADMIN)
    course = await _course(session)
    cs = await _session(
        session,
        course,
        admin,
        status=SessionStatus.SCHEDULED,
        scheduled_at=datetime.now(UTC) + timedelta(days=1),
    )
    await _login(client, "admin@x.com")

    r = await client.post(f"/api/admin/sessions/{cs.id}/end")
    assert r.status_code == 200
    assert r.json()["status"] == "ENDED"


@pytest.mark.asyncio
async def test_end_already_ended_session_409(client, session):
    admin = await _user(session, "admin@x.com", UserRole.ADMIN)
    course = await _course(session)
    cs = await _session(
        session,
        course,
        admin,
        status=SessionStatus.ENDED,
        scheduled_at=datetime.now(UTC) - timedelta(days=1),
    )
    await _login(client, "admin@x.com")

    r = await client.post(f"/api/admin/sessions/{cs.id}/end")
    assert r.status_code == 409


@pytest.mark.asyncio
async def test_end_unknown_session_404(client, session):
    await _user(session, "admin@x.com", UserRole.ADMIN)
    await _login(client, "admin@x.com")
    r = await client.post("/api/admin/sessions/nope/end")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_end_session_requires_admin(client, session):
    inst = await _user(session, "inst@x.com", UserRole.INSTRUCTOR)
    course = await _course(session)
    cs = await _session(
        session,
        course,
        inst,
        status=SessionStatus.LIVE,
        scheduled_at=datetime.now(UTC) - timedelta(minutes=30),
    )
    await _login(client, "inst@x.com")
    r = await client.post(f"/api/admin/sessions/{cs.id}/end")
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_end_session_triggers_reconcile(client, session, monkeypatch):
    calls: list[str] = []
    monkeypatch.setattr(
        attendance_tasks, "schedule_reconcile", lambda uuid: calls.append(uuid)
    )

    admin = await _user(session, "admin@x.com", UserRole.ADMIN)
    course = await _course(session)
    cs = await _session(
        session,
        course,
        admin,
        status=SessionStatus.LIVE,
        scheduled_at=datetime.now(UTC) - timedelta(minutes=30),
        zoom_id="123456789",
    )
    session.add(
        Meeting(
            zoom_uuid="uuid-end-1",
            zoom_meeting_id="123456789",
            ended_at=datetime.now(UTC) - timedelta(minutes=5),
        )
    )
    await session.commit()
    await _login(client, "admin@x.com")

    r = await client.post(f"/api/admin/sessions/{cs.id}/end")
    assert r.status_code == 200
    assert calls == ["uuid-end-1"]


# --- janitor ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_janitor_ends_stale_live_sessions(engine, session):
    admin = await _user(session, "admin@x.com", UserRole.ADMIN)
    course = await _course(session)
    stale = await _session(
        session,
        course,
        admin,
        status=SessionStatus.LIVE,
        scheduled_at=datetime.now(UTC) - timedelta(hours=3),
    )
    fresh = await _session(
        session,
        course,
        admin,
        status=SessionStatus.LIVE,
        scheduled_at=datetime.now(UTC) - timedelta(minutes=10),
    )

    maker = async_sessionmaker(engine, expire_on_commit=False)
    n = await session_tasks._run_janitor(session_factory=maker)
    assert n == 1

    await session.refresh(stale)
    await session.refresh(fresh)
    assert stale.status == SessionStatus.ENDED
    assert stale.ended_at is not None
    assert fresh.status == SessionStatus.LIVE  # not yet stale


# --- past filter excludes LIVE -----------------------------------------------


@pytest.mark.asyncio
async def test_past_filter_excludes_live(client, session):
    student = await _user(session, "stu@x.com", UserRole.STUDENT)
    course = await _course(session)
    session.add(Enrollment(user_id=student.id, course_id=course.id))
    await session.commit()

    admin = await _user(session, "admin@x.com", UserRole.ADMIN)
    ended = await _session(
        session,
        course,
        admin,
        status=SessionStatus.ENDED,
        scheduled_at=datetime.now(UTC) - timedelta(days=2),
    )
    live_past = await _session(
        session,
        course,
        admin,
        status=SessionStatus.LIVE,
        scheduled_at=datetime.now(UTC) - timedelta(hours=1),
    )

    await _login(client, "stu@x.com")
    r = await client.get("/api/sessions?status=past")
    assert r.status_code == 200
    ids = {s["id"] for s in r.json()}
    assert ended.id in ids
    assert live_past.id not in ids  # still LIVE → not "past"
