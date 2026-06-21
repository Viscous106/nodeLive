"""Assignment + grading routes.

Create/grade/list-submissions are instructor/admin only. Submitting requires
enrollment in the assignment's course. One submission per student (resubmit
replaces and resets the grade).
"""

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import get_current_user, require_role
from app.db.session import get_db
from app.models.assignment import Assignment, Submission, SubmissionStatus
from app.models.course import Enrollment
from app.models.user import User, UserRole
from app.schemas.assignment import (
    AssignmentCreate,
    AssignmentOut,
    SubmissionCreate,
    SubmissionGrade,
    SubmissionOut,
)
from app.utils.email import send_grade_notification

router = APIRouter(tags=["assignments"])

_instructor = require_role(UserRole.INSTRUCTOR, UserRole.ADMIN)


async def _assignment_or_404(db: AsyncSession, assignment_id: str) -> Assignment:
    a = await db.get(Assignment, assignment_id)
    if a is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Assignment not found")
    return a


@router.post(
    "/assignments",
    response_model=AssignmentOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_assignment(
    body: AssignmentCreate,
    user: User = Depends(_instructor),
    db: AsyncSession = Depends(get_db),
) -> Assignment:
    a = Assignment(
        course_id=body.course_id,
        session_id=body.session_id,
        title=body.title,
        description=body.description,
        due_at=body.due_at,
        max_points=body.max_points,
        created_by=user.id,
    )
    db.add(a)
    await db.commit()
    await db.refresh(a)
    return a


@router.get("/assignments", response_model=list[AssignmentOut])
async def list_assignments(
    session_id: str | None = Query(default=None, alias="sessionId"),
    course_id: str | None = Query(default=None, alias="courseId"),
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[Assignment]:
    stmt = select(Assignment)
    if session_id:
        stmt = stmt.where(Assignment.session_id == session_id)
    if course_id:
        stmt = stmt.where(Assignment.course_id == course_id)
    return list(await db.scalars(stmt.order_by(Assignment.created_at)))


@router.get("/assignments/{assignment_id}", response_model=AssignmentOut)
async def get_assignment(
    assignment_id: str,
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Assignment:
    return await _assignment_or_404(db, assignment_id)


@router.post(
    "/assignments/{assignment_id}/submissions",
    response_model=SubmissionOut,
    status_code=status.HTTP_201_CREATED,
)
async def submit(
    assignment_id: str,
    body: SubmissionCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Submission:
    assignment = await _assignment_or_404(db, assignment_id)

    enrolled = await db.scalar(
        select(Enrollment).where(
            Enrollment.user_id == user.id,
            Enrollment.course_id == assignment.course_id,
        )
    )
    if enrolled is None:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "You are not enrolled in this course"
        )

    existing = await db.scalar(
        select(Submission).where(
            Submission.assignment_id == assignment_id,
            Submission.user_id == user.id,
        )
    )
    if existing is not None:
        existing.content = body.content
        existing.status = SubmissionStatus.SUBMITTED
        existing.grade = None
        existing.feedback = None
        existing.graded_at = None
        sub = existing
    else:
        sub = Submission(
            assignment_id=assignment_id, user_id=user.id, content=body.content
        )
        db.add(sub)
    await db.commit()
    await db.refresh(sub)
    return sub


@router.get("/assignments/{assignment_id}/my-submission", response_model=SubmissionOut)
async def my_submission(
    assignment_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Submission:
    sub = await db.scalar(
        select(Submission).where(
            Submission.assignment_id == assignment_id,
            Submission.user_id == user.id,
        )
    )
    if sub is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No submission yet")
    return sub


@router.get(
    "/assignments/{assignment_id}/submissions",
    response_model=list[SubmissionOut],
)
async def list_submissions(
    assignment_id: str,
    _user: User = Depends(_instructor),
    db: AsyncSession = Depends(get_db),
) -> list[Submission]:
    return list(
        await db.scalars(
            select(Submission).where(Submission.assignment_id == assignment_id)
        )
    )


@router.patch("/submissions/{submission_id}", response_model=SubmissionOut)
async def grade_submission(
    submission_id: str,
    body: SubmissionGrade,
    _user: User = Depends(_instructor),
    db: AsyncSession = Depends(get_db),
) -> Submission:
    sub = await db.get(Submission, submission_id)
    if sub is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Submission not found")
    sub.grade = body.grade
    sub.feedback = body.feedback
    sub.status = SubmissionStatus.GRADED
    sub.graded_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(sub)

    student = await db.get(User, sub.user_id)
    assignment = await db.get(Assignment, sub.assignment_id)
    if student and assignment and student.email:
        await send_grade_notification(
            to=student.email,
            student_name=student.display_name,
            assignment_title=assignment.title,
            grade=sub.grade,
            max_points=assignment.max_points,
            feedback=sub.feedback,
        )

    return sub
