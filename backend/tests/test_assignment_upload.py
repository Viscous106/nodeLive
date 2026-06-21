"""POST /api/assignments/{id}/upload-url — presigned R2 upload."""

import pytest

from app.auth.security import hash_password
from app.models.assignment import Assignment
from app.models.course import Course, Enrollment
from app.models.user import User, UserRole
from app.services.roles import assign_role


async def _user(session, email, role=UserRole.STUDENT):
    u = User(
        email=email,
        hashed_password=hash_password("pass1234"),
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
    r = await client.post(
        "/api/auth/login", json={"email": email, "password": "pass1234"}
    )
    assert r.status_code == 200


async def _setup(session):
    instructor = await _user(session, "inst@x.com", UserRole.INSTRUCTOR)
    student = await _user(session, "stu@x.com", UserRole.STUDENT)
    course = Course(id="c1", title="CS101")
    session.add(course)
    await session.commit()
    assignment = Assignment(
        course_id="c1",
        title="Homework 1",
        created_by=instructor.id,
    )
    session.add(assignment)
    session.add(Enrollment(user_id=student.id, course_id="c1"))
    await session.commit()
    return instructor, student, assignment


@pytest.mark.asyncio
async def test_upload_url_501_when_r2_not_configured(client, session):
    instructor, student, assignment = await _setup(session)
    await _login(client, "stu@x.com")

    r = await client.post(
        f"/api/assignments/{assignment.id}/upload-url",
        params={"filename": "homework.pdf"},
    )
    assert r.status_code == 501


@pytest.mark.asyncio
async def test_upload_url_403_for_non_enrolled(client, session):
    instructor, _student, assignment = await _setup(session)
    await _user(session, "out@x.com", UserRole.STUDENT)
    await _login(client, "out@x.com")

    r = await client.post(
        f"/api/assignments/{assignment.id}/upload-url",
        params={"filename": "file.pdf"},
    )
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_upload_url_404_for_unknown_assignment(client, session):
    await _user(session, "stu@x.com", UserRole.STUDENT)
    await _login(client, "stu@x.com")

    r = await client.post(
        "/api/assignments/nonexistent/upload-url",
        params={"filename": "file.pdf"},
    )
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_upload_url_401_without_auth(client, session):
    _instructor, _student, assignment = await _setup(session)
    client.cookies.clear()

    r = await client.post(
        f"/api/assignments/{assignment.id}/upload-url",
        params={"filename": "file.pdf"},
    )
    assert r.status_code == 401
