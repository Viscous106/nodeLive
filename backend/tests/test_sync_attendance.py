"""Manual attendance sync: POST /api/admin/sessions/{id}/sync-attendance.

Pulls attendance straight from the Zoom Reports API (webhook-independent) and
surfaces a diagnostic. Zoom calls + reconcile are stubbed; the test exercises the
orchestration, Meeting-row upsert, and error surfacing.
"""

from datetime import UTC, datetime, timedelta

import httpx
import pytest
from sqlalchemy import select

from app.auth.security import hash_password
from app.models.attendance import Meeting
from app.models.course import ClassSession, Course
from app.models.user import User, UserRole
from app.services.roles import assign_role
from app.utils import zoom_meetings
from app.workers import attendance_tasks

_PW = "passphrase-sync-1"


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


async def _course(session, cid="c-sync", title="Sync"):
    c = Course(id=cid, title=title)
    session.add(c)
    await session.commit()
    return c


async def _session(session, course, host, zoom_id="83824294541"):
    cs = ClassSession(
        course_id=course.id,
        host_id=host.id,
        title="testing",
        scheduled_at=datetime.now(UTC) - timedelta(hours=1),
        duration_mins=60,
        zoom_meeting_id=zoom_id,
    )
    session.add(cs)
    await session.commit()
    return cs


async def _login(client, email):
    client.cookies.clear()
    r = await client.post("/api/auth/login", json={"email": email, "password": _PW})
    assert r.status_code == 200, r.text


@pytest.fixture
def _stub_zoom(monkeypatch):
    monkeypatch.setattr(zoom_meetings, "s2s_configured", lambda: True)


@pytest.mark.asyncio
async def test_sync_reconciles_and_upserts_meeting(
    client, session, monkeypatch, _stub_zoom
):
    monkeypatch.setattr(
        zoom_meetings, "get_past_instances", lambda n: _async_return(["uuid-A"])
    )
    calls: list[str] = []

    async def fake_reconcile(u):
        calls.append(u)
        return 2

    monkeypatch.setattr(attendance_tasks, "run_reconcile", fake_reconcile)

    admin = await _user(session, "admin@x.com", UserRole.ADMIN)
    course = await _course(session)
    cs = await _session(session, course, admin)
    await _login(client, "admin@x.com")

    r = await client.post(f"/api/admin/sessions/{cs.id}/sync-attendance")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] is True
    assert body["instances"] == 1
    assert body["attendees"] == 2
    assert calls == ["uuid-A"]
    # Meeting row upserted so the Attendance tab can resolve it.
    m = await session.scalar(select(Meeting).where(Meeting.zoom_uuid == "uuid-A"))
    assert m is not None and m.zoom_meeting_id == "83824294541"


@pytest.mark.asyncio
async def test_sync_no_zoom_meeting_id(client, session, _stub_zoom):
    admin = await _user(session, "admin@x.com", UserRole.ADMIN)
    course = await _course(session)
    cs = await _session(session, course, admin, zoom_id=None)
    await _login(client, "admin@x.com")

    r = await client.post(f"/api/admin/sessions/{cs.id}/sync-attendance")
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is False
    assert "Zoom meeting" in body["error"]


@pytest.mark.asyncio
async def test_sync_s2s_not_configured(client, session, monkeypatch):
    monkeypatch.setattr(zoom_meetings, "s2s_configured", lambda: False)
    admin = await _user(session, "admin@x.com", UserRole.ADMIN)
    course = await _course(session)
    cs = await _session(session, course, admin)
    await _login(client, "admin@x.com")

    r = await client.post(f"/api/admin/sessions/{cs.id}/sync-attendance")
    assert r.status_code == 200
    assert r.json()["ok"] is False


@pytest.mark.asyncio
async def test_sync_no_instances(client, session, monkeypatch, _stub_zoom):
    monkeypatch.setattr(
        zoom_meetings, "get_past_instances", lambda n: _async_return([])
    )
    admin = await _user(session, "admin@x.com", UserRole.ADMIN)
    course = await _course(session)
    cs = await _session(session, course, admin)
    await _login(client, "admin@x.com")

    r = await client.post(f"/api/admin/sessions/{cs.id}/sync-attendance")
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is False
    assert "instances" in body["error"].lower()


@pytest.mark.asyncio
async def test_sync_surfaces_zoom_http_error(client, session, monkeypatch, _stub_zoom):
    def raising(_n):
        req = httpx.Request("GET", "https://api.zoom.us")
        resp = httpx.Response(403, text="report scope required", request=req)
        raise httpx.HTTPStatusError("forbidden", request=req, response=resp)

    monkeypatch.setattr(zoom_meetings, "get_past_instances", raising)
    admin = await _user(session, "admin@x.com", UserRole.ADMIN)
    course = await _course(session)
    cs = await _session(session, course, admin)
    await _login(client, "admin@x.com")

    r = await client.post(f"/api/admin/sessions/{cs.id}/sync-attendance")
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is False
    assert "403" in body["error"]


@pytest.mark.asyncio
async def test_sync_404_unknown_session(client, session):
    await _user(session, "admin@x.com", UserRole.ADMIN)
    await _login(client, "admin@x.com")
    r = await client.post("/api/admin/sessions/nope/sync-attendance")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_sync_requires_admin(client, session):
    inst = await _user(session, "inst@x.com", UserRole.INSTRUCTOR)
    course = await _course(session)
    cs = await _session(session, course, inst)
    await _login(client, "inst@x.com")
    r = await client.post(f"/api/admin/sessions/{cs.id}/sync-attendance")
    assert r.status_code == 403


def _async_return(value):
    async def _coro():
        return value

    return _coro()
