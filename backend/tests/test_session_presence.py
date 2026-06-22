"""Socket-presence attendance (the free-Zoom-plan signal / webhook backstop).

Covers the presence open/close helpers and the admin attendance compute that
unions socket presence with the Zoom/webhook spans.
"""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.auth.security import hash_password
from app.models.attendance import AttendanceFinal, Meeting, SessionPresence
from app.models.course import ClassSession, Course, Enrollment
from app.models.user import User, UserRole
from app.services.roles import assign_role

_PW = "passphrase-presence"


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


async def _course(session, cid="c-pres", title="Presence"):
    c = Course(id=cid, title=title)
    session.add(c)
    await session.commit()
    return c


async def _session(session, course, host, *, zoom_id=None, ended_at=None):
    cs = ClassSession(
        course_id=course.id,
        host_id=host.id,
        title="testing",
        scheduled_at=datetime.now(UTC) - timedelta(hours=1),
        duration_mins=60,
        zoom_meeting_id=zoom_id,
        ended_at=ended_at,
    )
    session.add(cs)
    await session.commit()
    return cs


async def _login(client, email):
    client.cookies.clear()
    r = await client.post("/api/auth/login", json={"email": email, "password": _PW})
    assert r.status_code == 200, r.text


# --- presence helpers --------------------------------------------------------


@pytest.mark.asyncio
async def test_open_and_close_presence(session, engine, monkeypatch):
    from app.realtime import server

    maker = async_sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr(server, "AsyncSessionLocal", maker)

    await server._open_presence("sid-1", "sess-1", "user-1")
    row = await session.scalar(
        select(SessionPresence).where(SessionPresence.session_id == "sess-1")
    )
    assert row is not None and row.left_at is None

    await server._close_presence(row.id)
    await session.refresh(row)
    assert row.left_at is not None


# --- admin attendance compute -----------------------------------------------


@pytest.mark.asyncio
async def test_attendance_from_socket_presence_only(client, session):
    admin = await _user(session, "admin@x.com", UserRole.ADMIN)
    student = await _user(session, "stu@x.com", UserRole.STUDENT)
    course = await _course(session)
    cs = await _session(session, course, admin)  # no Zoom data at all
    session.add(Enrollment(user_id=student.id, course_id=course.id))
    session.add(
        SessionPresence(
            session_id=cs.id,
            user_id=student.id,
            joined_at=datetime.now(UTC) - timedelta(minutes=30),
            left_at=datetime.now(UTC),
        )
    )
    await session.commit()
    await _login(client, "admin@x.com")

    r = await client.get(f"/api/admin/sessions/{cs.id}/attendance")
    assert r.status_code == 200
    row = next(d for d in r.json() if d["userId"] == student.id)
    assert row["attended"] is True
    assert 1750 <= row["presentSeconds"] <= 1810  # ~30 min


@pytest.mark.asyncio
async def test_attendance_unions_zoom_and_socket_not_summed(client, session):
    admin = await _user(session, "admin@x.com", UserRole.ADMIN)
    student = await _user(session, "stu@x.com", UserRole.STUDENT)
    course = await _course(session)
    cs = await _session(session, course, admin, zoom_id="99887766")
    session.add(Enrollment(user_id=student.id, course_id=course.id))
    # Zoom span: t0 .. t0+1800 (30 min)
    t0 = 1_750_000_000
    session.add(Meeting(zoom_uuid="uuid-Z", zoom_meeting_id="99887766"))
    session.add(
        AttendanceFinal(
            zoom_uuid="uuid-Z",
            user_id=student.id,
            email="stu@x.com",
            present_seconds=1800,
            sessions=[[t0, t0 + 1800]],
        )
    )
    # Socket span overlaps + extends: t0+900 .. t0+2700
    session.add(
        SessionPresence(
            session_id=cs.id,
            user_id=student.id,
            joined_at=datetime.fromtimestamp(t0 + 900, UTC),
            left_at=datetime.fromtimestamp(t0 + 2700, UTC),
        )
    )
    await session.commit()
    await _login(client, "admin@x.com")

    r = await client.get(f"/api/admin/sessions/{cs.id}/attendance")
    row = next(d for d in r.json() if d["userId"] == student.id)
    # Union is t0..t0+2700 = 2700s — NOT 1800+1800 summed.
    assert row["presentSeconds"] == 2700


@pytest.mark.asyncio
async def test_open_presence_uses_session_ended_at_when_still_open(client, session):
    admin = await _user(session, "admin@x.com", UserRole.ADMIN)
    student = await _user(session, "stu@x.com", UserRole.STUDENT)
    course = await _course(session)
    ended = datetime.now(UTC) - timedelta(minutes=5)
    cs = await _session(session, course, admin, ended_at=ended)
    session.add(Enrollment(user_id=student.id, course_id=course.id))
    # left_at is NULL (disconnect missed) → compute caps at the session end.
    session.add(
        SessionPresence(
            session_id=cs.id,
            user_id=student.id,
            joined_at=ended - timedelta(minutes=10),
            left_at=None,
        )
    )
    await session.commit()
    await _login(client, "admin@x.com")

    r = await client.get(f"/api/admin/sessions/{cs.id}/attendance")
    row = next(d for d in r.json() if d["userId"] == student.id)
    assert 590 <= row["presentSeconds"] <= 610  # ~10 min, capped at ended_at
