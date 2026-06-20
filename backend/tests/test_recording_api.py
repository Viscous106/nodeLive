"""Session-scoped recording API: resolution, 404/501 gates, heartbeat union,
read-model shape, membership gating."""

from datetime import UTC, datetime

from app.auth.security import hash_password

_PW = "passphrase-1234"


async def _user(session, email, role="STUDENT"):
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


async def _seed(session, *, stored=True, zoom="82912345678", uuid="occ-1"):
    from app.models.attendance import Meeting
    from app.models.course import ClassSession, Course, SessionStatus
    from app.models.user import User, UserRole

    session.add(
        User(
            id="h1",
            email="host@x.com",
            hashed_password=hash_password(_PW),
            display_name="host",
            role=UserRole("INSTRUCTOR"),
        )
    )
    session.add(Course(id="c1", title="DB"))
    await session.flush()
    session.add(
        ClassSession(
            id="s1",
            course_id="c1",
            host_id="h1",
            title="Live",
            scheduled_at=datetime(2026, 7, 1, 10, tzinfo=UTC),
            duration_mins=60,
            zoom_meeting_id=zoom,
            status=SessionStatus.ENDED,
        )
    )
    m = Meeting(
        zoom_uuid=uuid,
        zoom_meeting_id=zoom,
        ended_at=datetime(2026, 7, 1, 11, tzinfo=UTC),
    )
    if stored:
        m.recording_s3_key = f"recordings/{uuid}.mp4"
        m.recording_status = "stored"
        m.recording_duration_secs = 100
    session.add(m)
    await session.commit()


async def _enroll(session, user_id):
    from app.models.course import Enrollment

    session.add(Enrollment(user_id=user_id, course_id="c1"))
    await session.commit()


async def test_url_501_when_r2_unconfigured(client, session, monkeypatch):
    import app.api.recordings as rec

    # Recording row is 'stored', but R2 creds are absent → 501 (not 404).
    monkeypatch.setattr(rec, "is_configured", lambda: False)
    uid = await _user(session, "a@x.com")
    await _seed(session)
    await _enroll(session, uid)
    await _login(client, "a@x.com")
    r = await client.get("/api/sessions/s1/recording/url")
    assert r.status_code == 501


async def test_url_404_when_no_recording(client, session, monkeypatch):
    import app.api.recordings as rec

    monkeypatch.setattr(rec, "is_configured", lambda: True)
    uid = await _user(session, "a@x.com")
    await _seed(session, stored=False)
    await _enroll(session, uid)
    await _login(client, "a@x.com")
    r = await client.get("/api/sessions/s1/recording/url")
    assert r.status_code == 404


async def test_url_presigns_when_configured(client, session, monkeypatch):
    import app.api.recordings as rec

    monkeypatch.setattr(rec, "is_configured", lambda: True)
    monkeypatch.setattr(
        rec, "presign_get", lambda key, ttl: f"https://signed/{key}?t={ttl}"
    )
    uid = await _user(session, "a@x.com")
    await _seed(session)
    await _enroll(session, uid)
    await _login(client, "a@x.com")
    r = await client.get("/api/sessions/s1/recording/url")
    assert r.status_code == 200
    assert r.json()["url"].startswith("https://signed/recordings/occ-1.mp4")


async def test_heartbeat_seek_to_end_partial_and_read_model(client, session):
    uid = await _user(session, "a@x.com")
    await _seed(session)
    await _enroll(session, uid)
    await _login(client, "a@x.com")
    # watch 0–15
    r = await client.post(
        "/api/sessions/s1/recording/heartbeat",
        json={"played_from": 0, "played_to": 15, "duration": 100},
    )
    assert r.status_code == 200
    # seek to end, watch 99–100 → 16%, not 100%
    r = await client.post(
        "/api/sessions/s1/recording/heartbeat",
        json={"played_from": 99, "played_to": 100, "duration": 100},
    )
    assert abs(r.json()["percent_complete"] - 0.16) < 1e-9
    # read-model
    ws = await client.get("/api/sessions/s1/recording/watch-status")
    body = ws.json()
    assert body["available"] is True
    assert abs(body["percent_complete"] - 0.16) < 1e-9
    assert body["last_position_secs"] == 100
    assert body["duration_secs"] == 100


async def test_heartbeat_uses_server_duration_over_client(client, session):
    # server duration is 100; a lying client says duration=20 → still /100.
    uid = await _user(session, "a@x.com")
    await _seed(session)
    await _enroll(session, uid)
    await _login(client, "a@x.com")
    r = await client.post(
        "/api/sessions/s1/recording/heartbeat",
        json={"played_from": 0, "played_to": 20, "duration": 20},
    )
    assert abs(r.json()["percent_complete"] - 0.20) < 1e-9  # 20/100, not 20/20


async def test_non_member_forbidden(client, session):
    await _user(session, "owner@x.com")
    await _seed(session)
    await _user(session, "stranger@x.com")
    await _login(client, "stranger@x.com")
    r = await client.get("/api/sessions/s1/recording/progress")
    assert r.status_code == 403
