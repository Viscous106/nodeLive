"""Enrollment helpers.

Single-org model: every member is a student of every course, so scheduled
sessions are visible to everyone on their dashboard. We realize that by keeping
the `enrollments` table fully populated — enrolling each user into every course
on login/signup, and every user into a course when it's created. Both helpers
are idempotent (they only insert the missing rows) and flush without committing,
so the caller owns the transaction boundary.

Selective per-course rosters are a future feature; for now visibility = org
membership.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.course import Course, Enrollment
from app.models.user import User


async def ensure_enrolled_all_courses(db: AsyncSession, user: User) -> int:
    """Enroll `user` into every course they're not already in. Returns the count
    of new enrollments created."""
    enrolled = set(
        await db.scalars(
            select(Enrollment.course_id).where(Enrollment.user_id == user.id)
        )
    )
    course_ids = list(await db.scalars(select(Course.id)))
    missing = [cid for cid in course_ids if cid not in enrolled]
    for cid in missing:
        db.add(Enrollment(user_id=user.id, course_id=cid))
    if missing:
        await db.flush()
    return len(missing)


async def enroll_all_users(db: AsyncSession, course_id: str) -> int:
    """Enroll every user into `course_id` (used when a course is created so the
    class is immediately visible to current members). Returns new enrollments."""
    already = set(
        await db.scalars(
            select(Enrollment.user_id).where(Enrollment.course_id == course_id)
        )
    )
    user_ids = list(await db.scalars(select(User.id)))
    missing = [uid for uid in user_ids if uid not in already]
    for uid in missing:
        db.add(Enrollment(user_id=uid, course_id=course_id))
    if missing:
        await db.flush()
    return len(missing)
