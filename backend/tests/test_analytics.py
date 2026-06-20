"""GET /api/sessions/:id/analytics — instructor session engagement."""

from datetime import UTC, datetime

from app.auth.security import hash_password

_PW = "passphrase-1234"


async def _user(session, email, role):
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


async def _seed(session, host_id, s1, s2):
    from app.models.course import ClassSession, Course, Enrollment, SessionStatus
    from app.models.live_meeting import (
        LeaderboardPoint,
        Poll,
        PollResponse,
        PollStatus,
        Quiz,
        QuizQuestion,
        QuizResponse,
        QuizStatus,
    )

    session.add(Course(id="c1", title="DB"))
    await session.flush()
    session.add(
        ClassSession(
            id="sess1",
            course_id="c1",
            host_id=host_id,
            title="Live",
            scheduled_at=datetime(2026, 7, 1, 10, 0, tzinfo=UTC),
            duration_mins=60,
            status=SessionStatus.LIVE,
        )
    )
    session.add_all(
        [Enrollment(user_id=s1, course_id="c1"), Enrollment(user_id=s2, course_id="c1")]
    )
    session.add(Quiz(id="q1", session_id="sess1", title="Q", status=QuizStatus.LIVE))
    await session.flush()
    session.add_all(
        [
            QuizQuestion(
                id="qq1",
                quiz_id="q1",
                text="a",
                options=["x", "y"],
                correct_index=0,
                position=0,
            ),
            QuizQuestion(
                id="qq2",
                quiz_id="q1",
                text="b",
                options=["x", "y"],
                correct_index=1,
                position=1,
            ),
        ]
    )
    await session.flush()
    session.add_all(
        [
            QuizResponse(
                question_id="qq1",
                user_id=s1,
                selected_index=0,
                is_correct=True,
                points=10,
            ),
            QuizResponse(
                question_id="qq2",
                user_id=s1,
                selected_index=1,
                is_correct=True,
                points=8,
            ),
            QuizResponse(
                question_id="qq1",
                user_id=s2,
                selected_index=1,
                is_correct=False,
                points=0,
            ),
        ]
    )
    session.add(
        Poll(
            id="p1",
            session_id="sess1",
            question="?",
            options=["a", "b"],
            status=PollStatus.OPEN,
        )
    )
    await session.flush()
    session.add_all(
        [
            PollResponse(poll_id="p1", user_id=s1, option_index=0),
            PollResponse(poll_id="p1", user_id=s2, option_index=1),
        ]
    )
    session.add_all(
        [
            LeaderboardPoint(session_id="sess1", user_id=s1, points=18),
            LeaderboardPoint(session_id="sess1", user_id=s2, points=7),
        ]
    )
    await session.commit()


async def test_instructor_analytics(client, session):
    host = await _user(session, "prof@example.com", "INSTRUCTOR")
    s1 = await _user(session, "a@example.com", "STUDENT")
    s2 = await _user(session, "b@example.com", "STUDENT")
    await _seed(session, host, s1, s2)
    await _login(client, "prof@example.com")

    r = await client.get("/api/sessions/sess1/analytics")
    assert r.status_code == 200
    b = r.json()
    assert b["enrolled"] == 2
    assert b["quizResponses"] == 3
    assert b["quizParticipants"] == 2
    assert b["pollResponses"] == 2
    assert b["avgQuizPoints"] == 6  # (10+8+0)/3 = 6
    assert b["topScorers"][0]["userId"] == s1
    assert b["topScorers"][0]["points"] == 18


async def test_student_cannot_view_analytics(client, session):
    host = await _user(session, "prof@example.com", "INSTRUCTOR")
    s1 = await _user(session, "a@example.com", "STUDENT")
    s2 = await _user(session, "b@example.com", "STUDENT")
    await _seed(session, host, s1, s2)
    await _login(client, "a@example.com")
    r = await client.get("/api/sessions/sess1/analytics")
    assert r.status_code == 403


async def test_analytics_requires_auth(client, session):
    host = await _user(session, "prof@example.com", "INSTRUCTOR")
    s1 = await _user(session, "a@example.com", "STUDENT")
    s2 = await _user(session, "b@example.com", "STUDENT")
    await _seed(session, host, s1, s2)
    client.cookies.clear()
    r = await client.get("/api/sessions/sess1/analytics")
    assert r.status_code == 401


async def test_analytics_empty_session(client, session):
    from app.models.course import ClassSession, Course, SessionStatus

    host = await _user(session, "prof@example.com", "INSTRUCTOR")
    session.add(Course(id="c1", title="DB"))
    await session.flush()
    session.add(
        ClassSession(
            id="empty",
            course_id="c1",
            host_id=host,
            title="L",
            scheduled_at=datetime(2026, 7, 1, 10, 0, tzinfo=UTC),
            duration_mins=60,
            status=SessionStatus.LIVE,
        )
    )
    await session.commit()
    await _login(client, "prof@example.com")
    r = await client.get("/api/sessions/empty/analytics")
    assert r.status_code == 200
    b = r.json()
    assert b["quizResponses"] == 0
    assert b["avgQuizPoints"] == 0
    assert b["topScorers"] == []
