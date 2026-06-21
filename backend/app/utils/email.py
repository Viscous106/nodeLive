"""SMTP email sender. Gracefully skips when SMTP_HOST is not configured."""

import asyncio
import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.core.config import settings

log = logging.getLogger(__name__)


def is_configured() -> bool:
    return bool(settings.SMTP_HOST)


def _send_sync(to: str, subject: str, body_text: str, body_html: str) -> None:
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = settings.SMTP_FROM
    msg["To"] = to
    msg.attach(MIMEText(body_text, "plain"))
    msg.attach(MIMEText(body_html, "html"))
    with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as smtp:
        smtp.starttls()
        if settings.SMTP_USERNAME:
            smtp.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
        smtp.sendmail(settings.SMTP_FROM, to, msg.as_string())


async def send_email(
    to: str, subject: str, body_text: str, body_html: str
) -> None:
    if not is_configured():
        return
    try:
        await asyncio.to_thread(_send_sync, to, subject, body_text, body_html)
    except Exception:
        log.exception("Failed to send email to %s", to)


async def send_grade_notification(
    to: str,
    student_name: str,
    assignment_title: str,
    grade: int,
    max_points: int,
    feedback: str | None,
) -> None:
    pct = round(grade / max_points * 100) if max_points else 0
    fb_text = f"\nFeedback: {feedback}" if feedback else ""
    fb_html = f"<p><strong>Feedback:</strong> {feedback}</p>" if feedback else ""
    body_text = (
        f"Hi {student_name},\n\n"
        f"Your submission for '{assignment_title}' has been graded.\n\n"
        f"Grade: {grade}/{max_points} ({pct}%){fb_text}\n\n"
        "— linkHQ"
    )
    body_html = (
        f"<p>Hi {student_name},</p>"
        f"<p>Your submission for <strong>{assignment_title}</strong>"
        " has been graded.</p>"
        f"<p><strong>Grade:</strong> {grade}/{max_points} ({pct}%)</p>"
        f"{fb_html}"
        "<p>— linkHQ</p>"
    )
    await send_email(
        to=to,
        subject=f"[linkHQ] Assignment graded: {assignment_title}",
        body_text=body_text,
        body_html=body_html,
    )


async def send_session_scheduled(
    recipients: list[tuple[str, str]],
    session_title: str,
    scheduled_at_str: str,
    course_title: str,
) -> None:
    if not is_configured() or not recipients:
        return
    body_text = (
        f"A new session has been scheduled in {course_title}:\n\n"
        f"{session_title}\n{scheduled_at_str}\n\n"
        "— linkHQ"
    )
    body_html = (
        f"<p>A new session has been scheduled in"
        f" <strong>{course_title}</strong>:</p>"
        f"<p><strong>{session_title}</strong><br>{scheduled_at_str}</p>"
        "<p>— linkHQ</p>"
    )
    for email, _name in recipients:
        await send_email(
            to=email,
            subject=f"[linkHQ] New session: {session_title}",
            body_text=body_text,
            body_html=body_html,
        )
