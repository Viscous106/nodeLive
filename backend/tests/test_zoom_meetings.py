"""ensure_meeting: reuse a real Zoom meeting, else create one. The live REST
calls (get_meeting/create_meeting) are stubbed — they need real S2S creds."""

import app.utils.zoom_meetings as zm


async def test_ensure_reuses_existing_meeting(monkeypatch):
    async def fake_get(mid):
        return {"id": mid, "password": "keep"}

    async def fake_create(topic):  # must not be called
        raise AssertionError("should not create when the meeting already exists")

    monkeypatch.setattr(zm, "get_meeting", fake_get)
    monkeypatch.setattr(zm, "create_meeting", fake_create)

    out = await zm.ensure_meeting("12345678", "DB Class")
    assert out == {"id": "12345678", "password": "keep"}


async def test_ensure_creates_when_missing(monkeypatch):
    async def fake_get(mid):  # 404 → None
        return None

    async def fake_create(topic):
        return {"id": 99001122, "password": "new"}

    monkeypatch.setattr(zm, "get_meeting", fake_get)
    monkeypatch.setattr(zm, "create_meeting", fake_create)

    out = await zm.ensure_meeting("8800000099", "DB Class")
    assert out == {"id": "99001122", "password": "new"}  # placeholder → real id


async def test_ensure_creates_when_no_current_id(monkeypatch):
    async def fake_create(topic):
        return {"id": 555, "password": ""}

    monkeypatch.setattr(zm, "create_meeting", fake_create)
    out = await zm.ensure_meeting(None, "DB Class")
    assert out["id"] == "555"


def test_is_configured_requires_host_email(monkeypatch):
    from app.core import config

    for a in ("ZOOM_S2S_ACCOUNT_ID", "ZOOM_S2S_CLIENT_ID", "ZOOM_S2S_CLIENT_SECRET"):
        monkeypatch.setattr(config.settings, a, "x")
    monkeypatch.setattr(config.settings, "ZOOM_HOST_EMAIL", "")
    assert zm.is_configured() is False
    monkeypatch.setattr(config.settings, "ZOOM_HOST_EMAIL", "host@zoom.me")
    assert zm.is_configured() is True
