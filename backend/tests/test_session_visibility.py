"""Scheduled sessions must be visible on every member's dashboard.

Single-org: creating a course enrolls all current members, and login backfills
enrollments for existing courses — so a session an admin schedules shows up in
the dashboard feeds (`/api/sessions`) for students and the admin alike.
"""

from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select

from app.auth.security import hash_password
from app.models.course import Course, Enrollment
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


async def _login(client, email):
    client.cookies.clear()
    r = await client.post("/api/auth/login", json={"email": email, "password": _PW})
    assert r.status_code == 200, r.text


def _future():
    return (datetime.now(UTC) + timedelta(days=1)).isoformat()


async def test_created_course_enrolls_all_users(client, session):
    await _user(session, "admin@x.com", UserRole.ADMIN)
    await _user(session, "stu@x.com", UserRole.STUDENT)
    await _login(client, "admin@x.com")

    r = await client.post("/api/admin/courses", json={"title": "DBMS"})
    assert r.status_code == 201
    cid = r.json()["id"]

    # both users are now enrolled in the new course
    count = await session.scalar(
        select(func.count()).select_from(Enrollment).where(Enrollment.course_id == cid)
    )
    assert count == 2


async def test_scheduled_session_visible_to_student_dashboard(client, session):
    await _user(session, "admin@x.com", UserRole.ADMIN)
    await _user(session, "stu@x.com", UserRole.STUDENT)

    # admin creates a course + schedules a session in it
    await _login(client, "admin@x.com")
    cid = (await client.post("/api/admin/courses", json={"title": "DBMS"})).json()["id"]
    sr = await client.post(
        "/api/sessions",
        json={"courseId": cid, "title": "Schema Design", "scheduledAt": _future()},
    )
    assert sr.status_code == 201

    # the student sees it on their upcoming-sessions feed
    await _login(client, "stu@x.com")
    upcoming = await client.get("/api/sessions?status=upcoming")
    assert upcoming.status_code == 200
    assert "Schema Design" in {s["title"] for s in upcoming.json()}


async def test_scheduling_into_legacy_course_enrolls_everyone(client, session):
    # a course created OUTSIDE the admin API (e.g. before the enroll-on-create
    # fix existed) has no enrollments — scheduling a session into it backfills.
    await _user(session, "admin@x.com", UserRole.ADMIN)
    student = await _user(session, "stu@x.com", UserRole.STUDENT)
    session.add(Course(id="c-legacy", title="Legacy"))
    await session.commit()

    pre = await session.scalar(
        select(func.count())
        .select_from(Enrollment)
        .where(Enrollment.user_id == student.id)
    )
    assert pre == 0

    await _login(client, "admin@x.com")
    sr = await client.post(
        "/api/sessions",
        json={
            "courseId": "c-legacy",
            "title": "Legacy Lecture",
            "scheduledAt": _future(),
        },
    )
    assert sr.status_code == 201

    # scheduling enrolled all users → the student sees it
    await _login(client, "stu@x.com")
    upcoming = await client.get("/api/sessions?status=upcoming")
    assert "Legacy Lecture" in {s["title"] for s in upcoming.json()}
