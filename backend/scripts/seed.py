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
from app.services.roles import assign_role, get_or_create_membership

_PASSWORD = "password123"
_COURSE_ID = "seed-course-dbms"
_INSTRUCTOR_ID = "seed-instructor"
_LIVE_SESSION_ID = "seed-session-live"


async def _ensure_live_session(db) -> None:
    """Create a LIVE session if one doesn't exist (idempotent). Lets both the
    instructor *and* enrolled students reach `/live/:id` for the demo."""
    if await db.get(ClassSession, _LIVE_SESSION_ID) is not None:
        return
    course_missing = await db.get(Course, _COURSE_ID) is None
    host_missing = await db.get(User, _INSTRUCTOR_ID) is None
    if course_missing or host_missing:
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
        # Reuse any existing seed rows. Look users up by EMAIL (the unique
        # constraint), not id: older deploys created these users with different
        # ids, so an id-only check misses them and re-inserts the same email →
        # `duplicate key value violates unique constraint "ix_users_email"`.
        instructor = await db.scalar(
            select(User).where(User.email == "instructor@linkhq.dev")
        )
        course = await db.get(Course, _COURSE_ID)

        if instructor is not None and course is not None:
            print("Seed data already present — ensuring a LIVE session.")
            await _ensure_live_session(db)
            return

        # --- users -----------------------------------------------------------
        if instructor is None:
            instructor = User(
                id=_INSTRUCTOR_ID,
                email="instructor@linkhq.dev",
                hashed_password=hash_password(_PASSWORD),
                display_name="Prof. Ada",
                role=UserRole.INSTRUCTOR,
            )
            db.add(instructor)

        students = []
        for i in (1, 2):
            email = f"student{i}@linkhq.dev"
            s = await db.scalar(select(User).where(User.email == email))
            if s is None:
                s = User(
                    id=f"seed-student-{i}",
                    email=email,
                    hashed_password=hash_password(_PASSWORD),
                    display_name=f"Student {i}",
                    role=UserRole.STUDENT,
                )
                db.add(s)
            students.append(s)

        # --- course ----------------------------------------------------------
        if course is None:
            course = Course(id=_COURSE_ID, title="Databases")
            db.add(course)

        await db.flush()

        # Default org + memberships. The seeded instructor is the org ADMIN so
        # the admin dashboard has someone to log in as (writes membership +
        # the User.role mirror together).
        await assign_role(db, instructor, UserRole.ADMIN)
        for s in students:
            await get_or_create_membership(db, s)

        # --- sessions (skip any that already exist) --------------------------
        now = datetime.now(UTC)
        sessions_added = 0
        for i in (1, 2):
            if await db.get(ClassSession, f"seed-session-up-{i}") is None:
                db.add(
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
                )
                sessions_added += 1
        for i in (1, 2, 3):
            if await db.get(ClassSession, f"seed-session-past-{i}") is None:
                db.add(
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
                )
                sessions_added += 1

        # --- enrollments (skip duplicates) -----------------------------------
        for u in (instructor, *students):
            existing_enr = await db.scalar(
                select(Enrollment).where(
                    Enrollment.user_id == u.id, Enrollment.course_id == course.id
                )
            )
            if existing_enr is None:
                db.add(Enrollment(user_id=u.id, course_id=course.id))

        await db.commit()
        await _ensure_live_session(db)

    print(
        f"Seed complete: {sessions_added} sessions created incl. LIVE "
        f"(password: {_PASSWORD})."
    )


if __name__ == "__main__":
    asyncio.run(seed())
