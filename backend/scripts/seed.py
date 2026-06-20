"""Seed local dev data: 1 instructor, 2 students, 1 course, 6 sessions
(one of them LIVE so the live-meeting page is click-through testable).

    python -m scripts.seed

Idempotent — the bulk seed runs once (keyed on the instructor), but a LIVE
session is *always* ensured so re-runs on an existing DB still get a joinable
class. Dev login password for all seeded users: ``password123``.
"""

import asyncio
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.auth.security import hash_password
from app.db.session import AsyncSessionLocal
from app.models.course import ClassSession, Course, Enrollment, SessionStatus
from app.models.user import User, UserRole

_PASSWORD = "password123"
_COURSE_ID = "seed-course-dbms"
_INSTRUCTOR_ID = "seed-instructor"
_LIVE_SESSION_ID = "seed-session-live"


async def _ensure_live_session(db) -> None:
    """Create a LIVE session if one doesn't exist (idempotent). Lets both the
    instructor *and* enrolled students reach `/live/:id` for the demo."""
    if await db.get(ClassSession, _LIVE_SESSION_ID) is not None:
        return
    db.add(
        ClassSession(
            id=_LIVE_SESSION_ID,
            course_id=_COURSE_ID,
            host_id=_INSTRUCTOR_ID,
            title="Live Now — Databases Demo",
            scheduled_at=datetime.now(UTC),
            duration_mins=90,
            zoom_meeting_id="8800000099",
            status=SessionStatus.LIVE,
        )
    )
    await db.commit()
    print(f"Ensured LIVE session '{_LIVE_SESSION_ID}' for live-page testing.")


async def seed() -> None:
    async with AsyncSessionLocal() as db:
        existing = await db.scalar(
            select(User).where(User.email == "instructor@linkhq.dev")
        )
        if existing is not None:
            print("Seed data already present — ensuring a LIVE session.")
            await _ensure_live_session(db)
            return

        instructor = User(
            id="seed-instructor",
            email="instructor@linkhq.dev",
            hashed_password=hash_password(_PASSWORD),
            display_name="Prof. Ada",
            role=UserRole.INSTRUCTOR,
        )
        students = [
            User(
                id=f"seed-student-{i}",
                email=f"student{i}@linkhq.dev",
                hashed_password=hash_password(_PASSWORD),
                display_name=f"Student {i}",
                role=UserRole.STUDENT,
            )
            for i in (1, 2)
        ]
        course = Course(id="seed-course-dbms", title="Databases")
        db.add_all([instructor, *students, course])
        await db.flush()

        now = datetime.now(UTC)
        sessions = [
            ClassSession(
                id=f"seed-session-up-{i}",
                course_id=course.id,
                host_id=instructor.id,
                title=f"Upcoming Lecture {i}",
                scheduled_at=now + timedelta(days=i),
                duration_mins=90,
                zoom_meeting_id=f"880000000{i}",
                status=SessionStatus.SCHEDULED,
            )
            for i in (1, 2)
        ] + [
            ClassSession(
                id=f"seed-session-past-{i}",
                course_id=course.id,
                host_id=instructor.id,
                title=f"Past Lecture {i}",
                scheduled_at=now - timedelta(days=i),
                duration_mins=90,
                zoom_meeting_id=f"770000000{i}",
                status=SessionStatus.ENDED,
            )
            for i in (1, 2, 3)
        ]
        db.add_all(sessions)
        db.add_all(
            Enrollment(user_id=u.id, course_id=course.id)
            for u in (instructor, *students)
        )
        await db.commit()
        await _ensure_live_session(db)

    print(
        "Seeded: 1 instructor, 2 students, 1 course, "
        f"{len(sessions) + 1} sessions incl. 1 LIVE (password: {_PASSWORD})."
    )


if __name__ == "__main__":
    asyncio.run(seed())
