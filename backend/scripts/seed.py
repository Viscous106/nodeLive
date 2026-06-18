"""Seed local dev data: 1 instructor, 2 students, 1 course, 5 sessions.

    python -m scripts.seed

Idempotent — re-running does nothing if the instructor already exists. Lets
Dev B exercise the live-meeting flow without provisioning real Zoom meetings.
Dev login password for all seeded users: ``password123``.
"""

import asyncio
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.auth.security import hash_password
from app.db.session import AsyncSessionLocal
from app.models.course import ClassSession, Course, Enrollment, SessionStatus
from app.models.user import User, UserRole

_PASSWORD = "password123"


async def seed() -> None:
    async with AsyncSessionLocal() as db:
        existing = await db.scalar(
            select(User).where(User.email == "instructor@linkhq.dev")
        )
        if existing is not None:
            print("Seed data already present — nothing to do.")
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

    print(
        "Seeded: 1 instructor, 2 students, 1 course, "
        f"{len(sessions)} sessions (password: {_PASSWORD})."
    )


if __name__ == "__main__":
    asyncio.run(seed())
