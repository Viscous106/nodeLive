"""GET /api/me/progress — student progress page data."""

from datetime import UTC, datetime, timedelta


async def _signup(client, email="stu@x.com"):
    r = await client.post(
        "/api/auth/signup",
        json={"email": email, "password": "passphrase123", "displayName": "Stu"},
    )
    return r.json()["id"]


async def _seed_course(session, user_id, course_id="c1", title="DB"):
    from app.models.assignment import Assignment, Submission, SubmissionStatus
    from app.models.course import ClassSession, Course, Enrollment, SessionStatus

    session.add(Course(id=course_id, title=title))
    await session.flush()
    session.add(Enrollment(user_id=user_id, course_id=course_id))
    session.add(
        Assignment(
            id=f"{course_id}-a1",
            course_id=course_id,
            title="HW 1",
            max_points=100,
            created_by=user_id,
        )
    )
    await session.flush()
    session.add(
        Submission(
            assignment_id=f"{course_id}-a1",
            user_id=user_id,
            content="my answer",
            status=SubmissionStatus.GRADED,
            grade=85,
            feedback="Good work",
            submitted_at=datetime.now(UTC),
        )
    )
    session.add(
        ClassSession(
            id=f"{course_id}-s1",
            course_id=course_id,
            host_id=user_id,
            title="Lecture 1",
            scheduled_at=datetime.now(UTC) - timedelta(days=1),
            status=SessionStatus.ENDED,
        )
    )
    await session.commit()


async def test_progress_no_enrollments(client):
    await _signup(client, "fresh@x.com")
    r = await client.get("/api/me/progress")
    assert r.status_code == 200
    b = r.json()
    assert b["courses"] == []
    assert b["assignmentsTotal"] == 0
    assert b["assignmentsSubmitted"] == 0
    assert b["assignmentsGraded"] == 0
    assert b["avgGrade"] is None


async def test_progress_with_graded_assignment(client, session):
    uid = await _signup(client)
    await _seed_course(session, uid)
    r = await client.get("/api/me/progress")
    assert r.status_code == 200
    b = r.json()
    assert len(b["courses"]) == 1
    course = b["courses"][0]
    assert course["title"] == "DB"
    assert len(course["assignments"]) == 1
    a = course["assignments"][0]
    assert a["title"] == "HW 1"
    assert a["status"] == "GRADED"
    assert a["grade"] == 85
    assert a["feedback"] == "Good work"
    assert b["assignmentsTotal"] == 1
    assert b["assignmentsSubmitted"] == 1
    assert b["assignmentsGraded"] == 1
    assert b["avgGrade"] == 85.0


async def test_progress_sessions_listed(client, session):
    uid = await _signup(client, "stu2@x.com")
    await _seed_course(session, uid, "c2", "Algo")
    r = await client.get("/api/me/progress")
    assert r.status_code == 200
    course = r.json()["courses"][0]
    assert len(course["sessions"]) == 1
    s = course["sessions"][0]
    assert s["title"] == "Lecture 1"
    assert s["sessionStatus"] == "ENDED"
    assert s["watchPercent"] is None  # no recording


async def test_progress_unsubmitted_assignment(client, session):
    from app.models.assignment import Assignment
    from app.models.course import Course, Enrollment

    uid = await _signup(client, "stu3@x.com")
    session.add(Course(id="c3", title="Math"))
    await session.flush()
    session.add(Enrollment(user_id=uid, course_id="c3"))
    session.add(
        Assignment(
            id="c3-a1",
            course_id="c3",
            title="Problem Set",
            max_points=50,
            created_by=uid,
        )
    )
    await session.commit()

    r = await client.get("/api/me/progress")
    assert r.status_code == 200
    b = r.json()
    a = b["courses"][0]["assignments"][0]
    assert a["status"] is None
    assert a["grade"] is None
    assert b["assignmentsSubmitted"] == 0
    assert b["avgGrade"] is None


async def test_progress_requires_auth(client):
    r = await client.get("/api/me/progress")
    assert r.status_code == 401
