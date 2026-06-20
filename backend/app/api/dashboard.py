"""Dashboard aggregate stats for the Performance widget."""

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import get_current_user
from app.db.session import get_db
from app.models.assignment import Submission, SubmissionStatus
from app.models.course import Enrollment
from app.models.user import User

router = APIRouter(tags=["dashboard"])


@router.get("/dashboard/stats")
async def dashboard_stats(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    graded = await db.scalar(
        select(func.count())
        .select_from(Submission)
        .where(
            Submission.user_id == user.id,
            Submission.status == SubmissionStatus.GRADED,
        )
    )
    total = await db.scalar(
        select(func.count())
        .select_from(Submission)
        .where(Submission.user_id == user.id)
    )
    courses = await db.scalar(
        select(func.count())
        .select_from(Enrollment)
        .where(Enrollment.user_id == user.id)
    )
    return {
        "assignmentsGraded": int(graded or 0),
        "assignmentsTotal": int(total or 0),
        "coursesEnrolled": int(courses or 0),
    }
