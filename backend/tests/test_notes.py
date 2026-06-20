"""Lecture notes — instructor posts session materials (links); students view."""

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


async def _session_row(session, host_id):
    from app.models.course import ClassSession, Course, SessionStatus

    session.add(Course(id="c1", title="DB"))
    await session.flush()
    session.add(
        ClassSession(
            id="s1",
            course_id="c1",
            host_id=host_id,
            title="Indexing",
            scheduled_at=datetime(2026, 7, 1, 10, 0, tzinfo=UTC),
            duration_mins=60,
            status=SessionStatus.ENDED,
        )
    )
    await session.commit()


async def _enroll(session, user_id):
    from app.models.course import Enrollment

    session.add(Enrollment(user_id=user_id, course_id="c1"))
    await session.commit()


async def _staff(client, session):
    iid = await _user(session, "prof@example.com", "INSTRUCTOR")
    await _session_row(session, iid)
    await _login(client, "prof@example.com")
    return iid


async def test_instructor_creates_note(client, session):
    await _staff(client, session)
    r = await client.post(
        "/api/sessions/s1/notes",
        json={"title": "Isolation Levels", "url": "https://drive/x", "kind": "PDF"},
    )
    assert r.status_code == 201
    b = r.json()
    assert b["title"] == "Isolation Levels"
    assert b["url"] == "https://drive/x"
    assert b["kind"] == "PDF"


async def test_note_kind_defaults_to_link(client, session):
    await _staff(client, session)
    r = await client.post(
        "/api/sessions/s1/notes", json={"title": "Slides", "url": "https://s"}
    )
    assert r.status_code == 201
    assert r.json()["kind"] == "LINK"


async def test_student_cannot_create_note(client, session):
    await _staff(client, session)
    await _user(session, "stu@example.com", "STUDENT")
    await _login(client, "stu@example.com")
    r = await client.post(
        "/api/sessions/s1/notes", json={"title": "x", "url": "https://x"}
    )
    assert r.status_code == 403


async def test_enrolled_student_lists_notes(client, session):
    await _staff(client, session)
    await client.post(
        "/api/sessions/s1/notes", json={"title": "Notes", "url": "https://n"}
    )
    sid = await _user(session, "stu@example.com", "STUDENT")
    await _enroll(session, sid)
    await _login(client, "stu@example.com")

    r = await client.get("/api/sessions/s1/notes")
    assert r.status_code == 200
    assert len(r.json()) == 1
    assert r.json()[0]["title"] == "Notes"


async def test_non_enrolled_cannot_list_notes(client, session):
    await _staff(client, session)
    await _user(session, "stu@example.com", "STUDENT")
    await _login(client, "stu@example.com")
    r = await client.get("/api/sessions/s1/notes")
    assert r.status_code == 403


async def test_notes_require_auth(client, session):
    await _staff(client, session)
    client.cookies.clear()
    r = await client.get("/api/sessions/s1/notes")
    assert r.status_code == 401
