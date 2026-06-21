"""AD — Sessions tab: admin list (all sessions), create (POST /api/sessions),
edit (PATCH), and cancel. Create/edit are INSTRUCTOR/ADMIN; the admin list +
cancel + course list are ADMIN-only.
"""

from datetime import UTC, datetime, timedelta

from app.auth.security import hash_password
from app.models.course import ClassSession, Course, SessionStatus
from app.models.user import User, UserRole
from app.services.roles import assign_role

_PW = "passphrase-1234"


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


async def _course(session, cid="c-dbms", title="Databases"):
    c = Course(id=cid, title=title)
    session.add(c)
    await session.commit()
    return c


async def _login(client, email):
    client.cookies.clear()
    r = await client.post("/api/auth/login", json={"email": email, "password": _PW})
    assert r.status_code == 200, r.text


def _when():
    return (datetime.now(UTC) + timedelta(days=1)).isoformat()


# --- create (POST /api/sessions) ---------------------------------------------


async def test_admin_creates_session(client, session):
    await _user(session, "admin@x.com", UserRole.ADMIN)
    await _course(session)
    await _login(client, "admin@x.com")

    r = await client.post(
        "/api/sessions",
        json={
            "courseId": "c-dbms",
            "title": "Indexes & B-Trees",
            "scheduledAt": _when(),
            "durationMins": 90,
            "zoomMeetingId": "8801234567",
        },
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["title"] == "Indexes & B-Trees"
    assert body["status"] == "SCHEDULED"
    assert body["zoomMeetingId"] == "8801234567"


async def test_create_session_unknown_course_404(client, session):
    await _user(session, "admin@x.com", UserRole.ADMIN)
    await _login(client, "admin@x.com")
    r = await client.post(
        "/api/sessions",
        json={"courseId": "nope", "title": "X", "scheduledAt": _when()},
    )
    assert r.status_code == 404


async def test_student_cannot_create_session(client, session):
    await _user(session, "stu@x.com", UserRole.STUDENT)
    await _course(session)
    await _login(client, "stu@x.com")
    r = await client.post(
        "/api/sessions",
        json={"courseId": "c-dbms", "title": "X", "scheduledAt": _when()},
    )
    assert r.status_code == 403


# --- admin list + filter ------------------------------------------------------


async def test_admin_lists_all_sessions_and_filters(client, session):
    admin = await _user(session, "admin@x.com", UserRole.ADMIN)
    await _course(session)
    session.add_all(
        [
            ClassSession(
                id="s-sched",
                course_id="c-dbms",
                host_id=admin.id,
                title="Scheduled one",
                scheduled_at=datetime.now(UTC) + timedelta(days=2),
                duration_mins=60,
                status=SessionStatus.SCHEDULED,
            ),
            ClassSession(
                id="s-ended",
                course_id="c-dbms",
                host_id=admin.id,
                title="Ended one",
                scheduled_at=datetime.now(UTC) - timedelta(days=2),
                duration_mins=60,
                status=SessionStatus.ENDED,
            ),
        ]
    )
    await session.commit()
    await _login(client, "admin@x.com")

    allr = await client.get("/api/admin/sessions")
    assert allr.status_code == 200
    assert {s["id"] for s in allr.json()} == {"s-sched", "s-ended"}

    sched = await client.get("/api/admin/sessions?status=SCHEDULED")
    assert {s["id"] for s in sched.json()} == {"s-sched"}


async def test_non_admin_cannot_list_admin_sessions(client, session):
    await _user(session, "stu@x.com", UserRole.STUDENT)
    await _login(client, "stu@x.com")
    assert (await client.get("/api/admin/sessions")).status_code == 403


# --- edit + cancel ------------------------------------------------------------


async def test_admin_edits_session(client, session):
    admin = await _user(session, "admin@x.com", UserRole.ADMIN)
    await _course(session)
    session.add(
        ClassSession(
            id="s-edit",
            course_id="c-dbms",
            host_id=admin.id,
            title="Old title",
            scheduled_at=datetime.now(UTC) + timedelta(days=1),
            duration_mins=60,
            status=SessionStatus.SCHEDULED,
        )
    )
    await session.commit()
    await _login(client, "admin@x.com")

    r = await client.patch(
        "/api/sessions/s-edit",
        json={"title": "New title", "durationMins": 120},
    )
    assert r.status_code == 200
    assert r.json()["title"] == "New title"
    assert r.json()["durationMins"] == 120


async def test_admin_cancels_session(client, session):
    admin = await _user(session, "admin@x.com", UserRole.ADMIN)
    await _course(session)
    session.add(
        ClassSession(
            id="s-cancel",
            course_id="c-dbms",
            host_id=admin.id,
            title="To cancel",
            scheduled_at=datetime.now(UTC) + timedelta(days=1),
            duration_mins=60,
            status=SessionStatus.SCHEDULED,
        )
    )
    await session.commit()
    await _login(client, "admin@x.com")

    r = await client.post("/api/admin/sessions/s-cancel/cancel")
    assert r.status_code == 200
    assert r.json()["status"] == "CANCELLED"


async def test_cancel_unknown_session_404(client, session):
    await _user(session, "admin@x.com", UserRole.ADMIN)
    await _login(client, "admin@x.com")
    assert (await client.post("/api/admin/sessions/nope/cancel")).status_code == 404


# --- admin course list (for the create form) ---------------------------------


async def test_admin_lists_courses(client, session):
    await _user(session, "admin@x.com", UserRole.ADMIN)
    await _course(session, "c-dbms", "Databases")
    await _course(session, "c-os", "Operating Systems")
    await _login(client, "admin@x.com")
    r = await client.get("/api/admin/courses")
    assert r.status_code == 200
    assert {c["title"] for c in r.json()} == {"Databases", "Operating Systems"}


async def test_admin_creates_course_then_schedules_into_it(client, session):
    await _user(session, "admin@x.com", UserRole.ADMIN)
    await _login(client, "admin@x.com")

    # no courses → create one through the UI path
    assert (await client.get("/api/admin/courses")).json() == []
    cr = await client.post("/api/admin/courses", json={"title": "Distributed Systems"})
    assert cr.status_code == 201
    course_id = cr.json()["id"]
    assert cr.json()["title"] == "Distributed Systems"

    # now a session can be scheduled into it
    sr = await client.post(
        "/api/sessions",
        json={"courseId": course_id, "title": "Raft", "scheduledAt": _when()},
    )
    assert sr.status_code == 201


async def test_create_course_blank_title_rejected(client, session):
    await _user(session, "admin@x.com", UserRole.ADMIN)
    await _login(client, "admin@x.com")
    r = await client.post("/api/admin/courses", json={"title": "   "})
    assert r.status_code == 422


async def test_non_admin_cannot_create_course(client, session):
    await _user(session, "stu@x.com", UserRole.STUDENT)
    await _login(client, "stu@x.com")
    r = await client.post("/api/admin/courses", json={"title": "X"})
    assert r.status_code == 403


async def test_admin_can_assign_student_as_host(client, session):
    # The scheduler may hand the host role to any member, incl. a student.
    admin = await _user(session, "admin2@x.com", UserRole.ADMIN)
    student = await _user(session, "presenter@x.com", UserRole.STUDENT)
    await _course(session, cid="c-host", title="Seminar")
    await _login(client, "admin2@x.com")

    r = await client.post(
        "/api/sessions",
        json={
            "courseId": "c-host",
            "title": "Student-led",
            "scheduledAt": datetime.now(UTC).isoformat(),
            "hostId": student.id,
        },
    )
    assert r.status_code == 201
    assert r.json()["hostId"] == student.id  # student is the designated host
    assert r.json()["hostId"] != admin.id
