"""GET /api/sessions/:id/live/state — reconnect snapshot."""

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


async def _session_row(session, host_id, sid="s1", cid="c1"):
    from app.models.course import ClassSession, Course, SessionStatus

    session.add(Course(id=cid, title="DB"))
    await session.flush()
    session.add(
        ClassSession(
            id=sid,
            course_id=cid,
            host_id=host_id,
            title="Live",
            scheduled_at=datetime(2026, 7, 1, 10, 0, tzinfo=UTC),
            duration_mins=60,
            status=SessionStatus.LIVE,
        )
    )
    await session.commit()


async def _seed_live(session, sid, user_id):
    from app.models.live_meeting import (
        Bookmark,
        CueCard,
        LeaderboardPoint,
        Notice,
        PinnedMessage,
        Poll,
        PollStatus,
        Quiz,
        QuizStatus,
    )

    now = datetime.now(UTC)
    session.add_all(
        [
            CueCard(
                id="cc1",
                session_id=sid,
                content="Welcome",
                display_order=0,
                shown_at=now,
            ),
            Poll(
                id="p1",
                session_id=sid,
                question="Fav DB?",
                options=["PG", "MySQL"],
                status=PollStatus.OPEN,
            ),
            Quiz(
                id="q1",
                session_id=sid,
                title="Indexes",
                time_limit_secs=30,
                status=QuizStatus.LIVE,
            ),
            PinnedMessage(
                id="pm1", session_id=sid, message="Reading: ch.5", pinned_by=user_id
            ),
            Notice(id="n1", session_id=sid, content="Break in 10", priority="NORMAL"),
            Bookmark(
                id="b1",
                session_id=sid,
                user_id=user_id,
                timestamp_ms=12000,
                label="key point",
            ),
            LeaderboardPoint(
                id="lp1", session_id=sid, user_id=user_id, points=8, reason="quiz"
            ),
        ]
    )
    await session.commit()


async def test_live_state_snapshot(client, session):
    uid = await _user(session, "stu@example.com")
    await _session_row(session, uid)
    await _seed_live(session, "s1", uid)
    await _login(client, "stu@example.com")

    resp = await client.get("/api/sessions/s1/live/state")
    assert resp.status_code == 200
    b = resp.json()
    assert b["currentCueCard"]["content"] == "Welcome"
    assert b["activePoll"]["question"] == "Fav DB?"
    assert b["activePoll"]["options"] == ["PG", "MySQL"]
    assert b["activeQuiz"]["title"] == "Indexes"
    assert b["pinnedMessage"] == "Reading: ch.5"
    assert any(n["content"] == "Break in 10" for n in b["recentNotices"])
    assert b["userBookmarks"][0]["timestampMs"] == 12000
    assert b["myQuizScore"] == 8
    assert b["leaderboard"][0]["userId"] == uid
    assert b["leaderboard"][0]["points"] == 8


async def test_live_state_empty(client, session):
    uid = await _user(session, "stu@example.com")
    await _session_row(session, uid)
    await _login(client, "stu@example.com")

    resp = await client.get("/api/sessions/s1/live/state")
    assert resp.status_code == 200
    b = resp.json()
    assert b["currentCueCard"] is None
    assert b["activePoll"] is None
    assert b["activeQuiz"] is None
    assert b["pinnedMessage"] is None
    assert b["recentNotices"] == []
    assert b["userBookmarks"] == []
    assert b["myQuizScore"] == 0
    assert b["leaderboard"] == []


async def test_live_state_requires_auth(client, session):
    uid = await _user(session, "stu@example.com")
    await _session_row(session, uid)
    client.cookies.clear()
    resp = await client.get("/api/sessions/s1/live/state")
    assert resp.status_code == 401


async def test_live_state_unknown_session_404(client, session):
    await _user(session, "stu@example.com")
    await _login(client, "stu@example.com")
    resp = await client.get("/api/sessions/nope/live/state")
    assert resp.status_code == 404
