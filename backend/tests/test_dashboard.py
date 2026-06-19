"""Dashboard data — enrolled courses + session lists (timetable, continue-watching)."""

from datetime import UTC, datetime, timedelta


async def _signup(client, email):
    r = await client.post(
        "/api/auth/signup",
        json={"email": email, "password": "passphrase here", "displayName": "U"},
    )
    return r.json()["id"]


async def _seed(session, user_id):
    """Enroll the user in c1 (with an upcoming + past session); leave c2 un-enrolled."""
    from app.models.course import ClassSession, Course, Enrollment, SessionStatus

    now = datetime.now(UTC)
    session.add_all(
        [Course(id="c1", title="Databases"), Course(id="c2", title="Networks")]
    )
    await session.flush()
    session.add(Enrollment(user_id=user_id, course_id="c1"))
    await session.flush()
    session.add_all(
        [
            ClassSession(
                id="up1",
                course_id="c1",
                host_id=user_id,
                title="Upcoming Lecture",
                scheduled_at=now + timedelta(days=1),
                duration_mins=90,
                status=SessionStatus.SCHEDULED,
            ),
            ClassSession(
                id="past1",
                course_id="c1",
                host_id=user_id,
                title="Past Lecture",
                scheduled_at=now - timedelta(days=2),
                duration_mins=90,
                status=SessionStatus.ENDED,
            ),
            ClassSession(
                id="other1",
                course_id="c2",  # user NOT enrolled here
                host_id=user_id,
                title="Other Course Lecture",
                scheduled_at=now + timedelta(days=1),
                duration_mins=90,
                status=SessionStatus.SCHEDULED,
            ),
        ]
    )
    await session.commit()


async def test_courses_returns_only_enrolled(client, session):
    uid = await _signup(client, "a@example.com")
    await _seed(session, uid)
    r = await client.get("/api/courses")
    assert r.status_code == 200
    assert [c["id"] for c in r.json()] == ["c1"]


async def test_courses_requires_auth(client):
    r = await client.get("/api/courses")
    assert r.status_code == 401


async def test_upcoming_sessions_are_enrolled_and_future(client, session):
    uid = await _signup(client, "a@example.com")
    await _seed(session, uid)
    r = await client.get("/api/sessions?status=upcoming")
    assert r.status_code == 200
    assert {s["id"] for s in r.json()} == {"up1"}


async def test_past_sessions_are_enrolled_and_past(client, session):
    uid = await _signup(client, "a@example.com")
    await _seed(session, uid)
    r = await client.get("/api/sessions?status=past")
    assert r.status_code == 200
    assert {s["id"] for s in r.json()} == {"past1"}


async def test_this_week_excludes_past_and_unenrolled(client, session):
    uid = await _signup(client, "a@example.com")
    await _seed(session, uid)
    r = await client.get("/api/sessions/this-week")
    assert r.status_code == 200
    ids = {s["id"] for s in r.json()}
    assert "up1" in ids
    assert "past1" not in ids
    assert "other1" not in ids
