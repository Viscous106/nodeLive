"""Assignment file upload/download — presigned R2 URLs.

POST /api/assignments/{id}/upload-url  (presigned PUT)
GET  /api/submissions/{id}/file-url    (presigned GET, for download)
Both degrade to 501 when R2 is unconfigured. The presign success path needs real
R2, so here we cover auth + the graceful-degrade seam, plus the key builder.
"""

import re

import pytest

from app.api.assignments import _FILE_PREFIX, _submission_object_key
from app.auth.security import hash_password
from app.models.assignment import Assignment, Submission
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


async def _submission(session, assignment_id, user_id, content):
    sub = Submission(assignment_id=assignment_id, user_id=user_id, content=content)
    session.add(sub)
    await session.commit()
    await session.refresh(sub)
    return sub


# --- upload-url (presigned PUT) ----------------------------------------------


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


# --- file-url (presigned GET, for download) ----------------------------------


@pytest.mark.asyncio
async def test_file_url_404_for_text_submission(client, session):
    _inst, student, assignment = await _setup(session)
    sub = await _submission(session, assignment.id, student.id, "just some typed text")
    await _login(client, "stu@x.com")

    r = await client.get(f"/api/submissions/{sub.id}/file-url")
    assert r.status_code == 404  # not a file submission


@pytest.mark.asyncio
async def test_file_url_403_for_other_student(client, session):
    _inst, student, assignment = await _setup(session)
    key = f"{_FILE_PREFIX}{assignment.id}/{student.id}/abc-homework.pdf"
    sub = await _submission(session, assignment.id, student.id, key)
    await _user(session, "other@x.com", UserRole.STUDENT)
    await _login(client, "other@x.com")

    r = await client.get(f"/api/submissions/{sub.id}/file-url")
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_file_url_501_when_r2_off_for_owner(client, session):
    _inst, student, assignment = await _setup(session)
    key = f"{_FILE_PREFIX}{assignment.id}/{student.id}/abc-homework.pdf"
    sub = await _submission(session, assignment.id, student.id, key)
    await _login(client, "stu@x.com")

    r = await client.get(f"/api/submissions/{sub.id}/file-url")
    assert r.status_code == 501  # owner passes authz; R2 unconfigured → 501


@pytest.mark.asyncio
async def test_file_url_staff_passes_authz(client, session):
    # Instructor (not the owner) still passes authz and reaches the 501 seam.
    _inst, student, assignment = await _setup(session)
    key = f"{_FILE_PREFIX}{assignment.id}/{student.id}/abc-homework.pdf"
    sub = await _submission(session, assignment.id, student.id, key)
    await _login(client, "inst@x.com")

    r = await client.get(f"/api/submissions/{sub.id}/file-url")
    assert r.status_code == 501


@pytest.mark.asyncio
async def test_file_url_404_for_unknown_submission(client, session):
    await _user(session, "stu@x.com", UserRole.STUDENT)
    await _login(client, "stu@x.com")

    r = await client.get("/api/submissions/nonexistent/file-url")
    assert r.status_code == 404


# --- key builder (unit) ------------------------------------------------------


def test_submission_object_key_sanitizes_and_namespaces():
    key = _submission_object_key("a1", "u1", "../../etc/p a$$wd.pdf")
    assert key.startswith(f"{_FILE_PREFIX}a1/u1/")
    tail = key.rsplit("/", 1)[1]
    # Path separators are stripped so the name can't escape its namespace; only
    # [A-Za-z0-9._-] survive (dots may remain, but without "/" they can't traverse).
    assert "/" not in tail
    assert re.fullmatch(r"[a-zA-Z0-9._-]+", tail)


def test_submission_object_key_blank_filename_falls_back():
    key = _submission_object_key("a1", "u1", "@@@")
    assert key.startswith(f"{_FILE_PREFIX}a1/u1/")
    assert re.fullmatch(r"[a-zA-Z0-9._-]+", key.rsplit("/", 1)[1])
