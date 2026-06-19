"""Assignments & grading — create (instructor), submit (enrolled student), grade."""

from datetime import UTC, datetime

from app.auth.security import hash_password

_PW = "passphrase-1234"


async def _user(session, email, role):
    """Insert a user with a role and return its id (does not log in)."""
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


async def _course_and_session(session, host_id):
    from app.models.course import ClassSession, Course, SessionStatus

    session.add(Course(id="c1", title="Databases"))
    await session.flush()
    session.add(
        ClassSession(
            id="s1",
            course_id="c1",
            host_id=host_id,
            title="Indexing",
            scheduled_at=datetime(2026, 7, 1, 10, 0, tzinfo=UTC),
            duration_mins=60,
            status=SessionStatus.SCHEDULED,
        )
    )
    await session.commit()


async def _enroll(session, user_id, course_id="c1"):
    from app.models.course import Enrollment

    session.add(Enrollment(user_id=user_id, course_id=course_id))
    await session.commit()


async def _create_assignment(client):
    return await client.post(
        "/api/assignments",
        json={
            "courseId": "c1",
            "sessionId": "s1",
            "title": "Build a B-tree",
            "description": "Implement insert + search.",
            "maxPoints": 100,
        },
    )


# --- create / authz ---------------------------------------------------------


async def test_instructor_creates_assignment(client, session):
    iid = await _user(session, "prof@example.com", "INSTRUCTOR")
    await _course_and_session(session, iid)
    await _login(client, "prof@example.com")

    resp = await _create_assignment(client)

    assert resp.status_code == 201
    body = resp.json()
    assert body["title"] == "Build a B-tree"
    assert body["courseId"] == "c1"
    assert body["sessionId"] == "s1"
    assert body["maxPoints"] == 100


async def test_student_cannot_create_assignment(client, session):
    iid = await _user(session, "prof@example.com", "INSTRUCTOR")
    await _course_and_session(session, iid)
    await _user(session, "stu@example.com", "STUDENT")
    await _login(client, "stu@example.com")

    resp = await _create_assignment(client)
    assert resp.status_code == 403


async def test_create_requires_auth(client, session):
    iid = await _user(session, "prof@example.com", "INSTRUCTOR")
    await _course_and_session(session, iid)
    client.cookies.clear()
    resp = await _create_assignment(client)
    assert resp.status_code == 401


# --- list -------------------------------------------------------------------


async def test_list_assignments_by_session(client, session):
    iid = await _user(session, "prof@example.com", "INSTRUCTOR")
    await _course_and_session(session, iid)
    await _login(client, "prof@example.com")
    await _create_assignment(client)
    await _create_assignment(client)

    resp = await client.get("/api/assignments?sessionId=s1")
    assert resp.status_code == 200
    assert len(resp.json()) == 2


# --- submit -----------------------------------------------------------------


async def _make_assignment_and_student(client, session):
    iid = await _user(session, "prof@example.com", "INSTRUCTOR")
    await _course_and_session(session, iid)
    await _login(client, "prof@example.com")
    aid = (await _create_assignment(client)).json()["id"]
    sid = await _user(session, "stu@example.com", "STUDENT")
    return aid, sid


async def test_enrolled_student_submits(client, session):
    aid, sid = await _make_assignment_and_student(client, session)
    await _enroll(session, sid)
    await _login(client, "stu@example.com")

    resp = await client.post(
        f"/api/assignments/{aid}/submissions",
        json={"content": "https://github.com/stu/btree"},
    )
    assert resp.status_code == 201
    assert resp.json()["status"] == "SUBMITTED"
    assert resp.json()["content"] == "https://github.com/stu/btree"


async def test_resubmit_updates_existing(client, session):
    aid, sid = await _make_assignment_and_student(client, session)
    await _enroll(session, sid)
    await _login(client, "stu@example.com")

    await client.post(f"/api/assignments/{aid}/submissions", json={"content": "v1"})
    await client.post(f"/api/assignments/{aid}/submissions", json={"content": "v2"})

    listing = await client.get(f"/api/assignments/{aid}/my-submission")
    assert listing.status_code == 200
    assert listing.json()["content"] == "v2"


async def test_non_enrolled_student_cannot_submit(client, session):
    aid, _sid = await _make_assignment_and_student(client, session)
    await _login(client, "stu@example.com")  # never enrolled

    resp = await client.post(
        f"/api/assignments/{aid}/submissions", json={"content": "x"}
    )
    assert resp.status_code == 403


# --- grade ------------------------------------------------------------------


async def _submit(client, session, aid, sid):
    await _enroll(session, sid)
    await _login(client, "stu@example.com")
    r = await client.post(
        f"/api/assignments/{aid}/submissions", json={"content": "work"}
    )
    return r.json()["id"]


async def test_instructor_grades_submission(client, session):
    aid, sid = await _make_assignment_and_student(client, session)
    sub_id = await _submit(client, session, aid, sid)

    await _login(client, "prof@example.com")
    resp = await client.patch(
        f"/api/submissions/{sub_id}", json={"grade": 85, "feedback": "Solid."}
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "GRADED"
    assert resp.json()["grade"] == 85
    assert resp.json()["feedback"] == "Solid."


async def test_student_cannot_grade(client, session):
    aid, sid = await _make_assignment_and_student(client, session)
    sub_id = await _submit(client, session, aid, sid)  # leaves client as student

    resp = await client.patch(f"/api/submissions/{sub_id}", json={"grade": 99})
    assert resp.status_code == 403


async def test_student_sees_their_grade(client, session):
    aid, sid = await _make_assignment_and_student(client, session)
    sub_id = await _submit(client, session, aid, sid)
    await _login(client, "prof@example.com")
    await client.patch(f"/api/submissions/{sub_id}", json={"grade": 70})

    await _login(client, "stu@example.com")
    resp = await client.get(f"/api/assignments/{aid}/my-submission")
    assert resp.status_code == 200
    assert resp.json()["grade"] == 70
    assert resp.json()["status"] == "GRADED"


async def test_instructor_lists_submissions(client, session):
    aid, sid = await _make_assignment_and_student(client, session)
    await _submit(client, session, aid, sid)
    await _login(client, "prof@example.com")

    resp = await client.get(f"/api/assignments/{aid}/submissions")
    assert resp.status_code == 200
    assert len(resp.json()) == 1
