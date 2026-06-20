"""GET /api/dashboard/stats — real numbers for the Performance widget."""


async def _signup(client, email="stu@example.com"):
    r = await client.post(
        "/api/auth/signup",
        json={"email": email, "password": "passphrase here", "displayName": "Stu"},
    )
    return r.json()["id"]


async def _seed(session, user_id):
    from app.models.assignment import Assignment, Submission, SubmissionStatus
    from app.models.course import Course, Enrollment

    session.add(Course(id="c1", title="DB"))
    await session.flush()
    session.add(Enrollment(user_id=user_id, course_id="c1"))
    session.add_all(
        [
            Assignment(id="a1", course_id="c1", title="A1", created_by=user_id),
            Assignment(id="a2", course_id="c1", title="A2", created_by=user_id),
        ]
    )
    await session.flush()
    session.add_all(
        [
            Submission(
                assignment_id="a1",
                user_id=user_id,
                content="x",
                status=SubmissionStatus.GRADED,
                grade=90,
            ),
            Submission(
                assignment_id="a2",
                user_id=user_id,
                content="y",
                status=SubmissionStatus.SUBMITTED,
            ),
        ]
    )
    await session.commit()


async def test_dashboard_stats_counts(client, session):
    uid = await _signup(client)
    await _seed(session, uid)
    r = await client.get("/api/dashboard/stats")
    assert r.status_code == 200
    b = r.json()
    assert b["assignmentsGraded"] == 1
    assert b["assignmentsTotal"] == 2
    assert b["coursesEnrolled"] == 1


async def test_dashboard_stats_zero_for_new_user(client):
    await _signup(client, "fresh@example.com")
    r = await client.get("/api/dashboard/stats")
    assert r.status_code == 200
    assert r.json() == {
        "assignmentsGraded": 0,
        "assignmentsTotal": 0,
        "coursesEnrolled": 0,
    }


async def test_dashboard_stats_requires_auth(client):
    r = await client.get("/api/dashboard/stats")
    assert r.status_code == 401
