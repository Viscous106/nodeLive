"""Email notification integration tests.

smtplib.SMTP is mocked so no real server needed. Tests verify:
- send_email skips (no SMTP_HOST) or calls SMTP correctly
- Grading a submission triggers the notification
"""

from unittest.mock import MagicMock, patch

# ─── utility unit tests ──────────────────────────────────────────────────────


async def test_send_email_skips_when_unconfigured():
    from app.utils.email import send_email

    with patch("app.utils.email.settings") as mock_settings:
        mock_settings.SMTP_HOST = ""
        with patch("smtplib.SMTP") as mock_smtp:
            await send_email("a@b.com", "hi", "text", "<p>html</p>")
            mock_smtp.assert_not_called()


async def test_send_email_calls_smtp_when_configured():
    from app.utils.email import send_email

    mock_instance = MagicMock()
    mock_ctx = MagicMock()
    mock_ctx.__enter__ = MagicMock(return_value=mock_instance)
    mock_ctx.__exit__ = MagicMock(return_value=False)

    with patch("app.utils.email.settings") as mock_settings:
        mock_settings.SMTP_HOST = "smtp.example.com"
        mock_settings.SMTP_PORT = 587
        mock_settings.SMTP_USERNAME = "user"
        mock_settings.SMTP_PASSWORD = "pass"
        mock_settings.SMTP_FROM = "noreply@linkhq.app"
        with patch("smtplib.SMTP", return_value=mock_ctx):
            await send_email("stu@x.com", "Test", "body", "<p>body</p>")
            mock_instance.starttls.assert_called_once()
            mock_instance.login.assert_called_once_with("user", "pass")
            mock_instance.sendmail.assert_called_once()


# ─── route-level integration tests ───────────────────────────────────────────


async def _setup_grading(client, session):
    from app.models.assignment import Assignment, Submission, SubmissionStatus
    from app.models.course import Course, Enrollment
    from app.models.user import User, UserRole

    r = await client.post(
        "/api/auth/signup",
        json={
            "email": "inst@x.com",
            "password": "pw12345678",
            "displayName": "Instructor",
        },
    )
    inst_id = r.json()["id"]

    r2 = await client.post(
        "/api/auth/signup",
        json={
            "email": "stu@x.com",
            "password": "pw12345678",
            "displayName": "Student",
        },
    )
    stu_id = r2.json()["id"]

    inst = await session.get(User, inst_id)
    inst.role = UserRole.INSTRUCTOR
    session.add(Course(id="c1", title="Math"))
    await session.flush()
    session.add(Enrollment(user_id=stu_id, course_id="c1"))
    session.add(
        Assignment(
            id="a1",
            course_id="c1",
            title="HW 1",
            max_points=100,
            created_by=inst_id,
        )
    )
    await session.flush()
    session.add(
        Submission(
            id="sub1",
            assignment_id="a1",
            user_id=stu_id,
            content="my work",
            status=SubmissionStatus.SUBMITTED,
        )
    )
    await session.commit()

    await client.post(
        "/api/auth/login",
        json={"email": "inst@x.com", "password": "pw12345678"},
    )
    return "sub1"


async def test_grading_triggers_email(client, session):
    sub_id = await _setup_grading(client, session)

    sent = []

    async def fake_send(
        to, student_name, assignment_title, grade, max_points, feedback
    ):
        sent.append({"to": to, "grade": grade, "title": assignment_title})

    with patch("app.api.assignments.send_grade_notification", side_effect=fake_send):
        r = await client.patch(
            f"/api/submissions/{sub_id}",
            json={"grade": 92, "feedback": "Excellent"},
        )
    assert r.status_code == 200
    assert len(sent) == 1
    assert sent[0]["to"] == "stu@x.com"
    assert sent[0]["grade"] == 92
    assert sent[0]["title"] == "HW 1"


async def test_grading_email_skipped_without_smtp(client, session):
    sub_id = await _setup_grading(client, session)

    with patch("app.utils.email.settings") as ms:
        ms.SMTP_HOST = ""
        with patch("smtplib.SMTP") as mock_smtp:
            r = await client.patch(
                f"/api/submissions/{sub_id}",
                json={"grade": 80},
            )
    assert r.status_code == 200
    mock_smtp.assert_not_called()
