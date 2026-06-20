"""GET /api/leaderboard — global ranking by summed leaderboard points."""

from datetime import UTC, datetime

from app.auth.security import hash_password

_PW = "passphrase-1234"


async def _user(session, email):
    from app.models.user import User, UserRole

    u = User(
        email=email,
        hashed_password=hash_password(_PW),
        display_name=email.split("@")[0],
        role=UserRole.STUDENT,
    )
    session.add(u)
    await session.commit()
    return u.id


async def _login(client, email):
    client.cookies.clear()
    await client.post("/api/auth/login", json={"email": email, "password": _PW})


async def _session_row(session, host_id, sid):
    from app.models.course import ClassSession, Course, SessionStatus

    existing = await session.get(Course, "c1")
    if existing is None:
        session.add(Course(id="c1", title="DB"))
        await session.flush()
    session.add(
        ClassSession(
            id=sid,
            course_id="c1",
            host_id=host_id,
            title="Live",
            scheduled_at=datetime(2026, 7, 1, 10, 0, tzinfo=UTC),
            duration_mins=60,
            status=SessionStatus.ENDED,
        )
    )
    await session.commit()


async def _points(session, session_id, user_id, points):
    from app.models.live_meeting import LeaderboardPoint

    session.add(LeaderboardPoint(session_id=session_id, user_id=user_id, points=points))
    await session.commit()


async def test_global_leaderboard_sums_across_sessions(client, session):
    host = await _user(session, "host@example.com")
    await _session_row(session, host, "s1")
    await _session_row(session, host, "s2")
    alice = await _user(session, "alice@example.com")
    bob = await _user(session, "bob@example.com")
    # alice: 6 + 4 = 10 across two sessions; bob: 7
    await _points(session, "s1", alice, 6)
    await _points(session, "s2", alice, 4)
    await _points(session, "s1", bob, 7)

    await _login(client, "alice@example.com")
    r = await client.get("/api/leaderboard")
    assert r.status_code == 200
    board = r.json()
    assert [row["userId"] for row in board] == [alice, bob]
    assert board[0]["points"] == 10
    assert board[1]["points"] == 7


async def test_leaderboard_empty(client, session):
    await _user(session, "alice@example.com")
    await _login(client, "alice@example.com")
    r = await client.get("/api/leaderboard")
    assert r.status_code == 200
    assert r.json() == []


async def test_leaderboard_requires_auth(client):
    r = await client.get("/api/leaderboard")
    assert r.status_code == 401
