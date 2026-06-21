"""Assignment + grading routes.

Create/grade/list-submissions are instructor/admin only. Submitting requires
enrollment in the assignment's course. One submission per student (resubmit
replaces and resets the grade).
"""

import re
import uuid
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
    FileUrlOut,
    SubmissionCreate,
    SubmissionGrade,
    SubmissionOut,
    UploadUrlOut,
)
from app.utils.recording_storage import is_configured, presign_get, presign_put

router = APIRouter(tags=["assignments"])

_instructor = require_role(UserRole.INSTRUCTOR, UserRole.ADMIN)

# File submissions store their R2 object key in `Submission.content`, namespaced
# under this prefix so the UI (and the download route) can tell a file apart from
# a typed/linked text submission.
_FILE_PREFIX = "submissions/"


async def _assignment_or_404(db: AsyncSession, assignment_id: str) -> Assignment:
    a = await db.get(Assignment, assignment_id)
    if a is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Assignment not found")
    return a


def _submission_object_key(assignment_id: str, user_id: str, filename: str) -> str:
    """A collision-proof, traversal-proof R2 key for an uploaded submission."""
    safe_name = re.sub(r"[^a-zA-Z0-9._-]", "_", filename)[:200] or "file"
    return f"{_FILE_PREFIX}{assignment_id}/{user_id}/{uuid.uuid4()}-{safe_name}"


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


@router.post(
    "/assignments/{assignment_id}/upload-url",
    response_model=UploadUrlOut,
)
async def get_upload_url(
    assignment_id: str,
    filename: str = Query(...),
    content_type: str = Query(
        default="application/octet-stream", alias="contentType"
    ),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UploadUrlOut:
    assignment = await _assignment_or_404(db, assignment_id)

    is_staff = user.role in (UserRole.INSTRUCTOR, UserRole.ADMIN)
    if not is_staff:
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

    if not is_configured():
        raise HTTPException(
            status.HTTP_501_NOT_IMPLEMENTED,
            "File storage not configured — submit a link or text instead",
        )

    key = _submission_object_key(assignment_id, user.id, filename)
    upload_url = presign_put(key, content_type)
    return UploadUrlOut(upload_url=upload_url, file_key=key)


@router.get("/submissions/{submission_id}/file-url", response_model=FileUrlOut)
async def get_submission_file_url(
    submission_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> FileUrlOut:
    """Presigned GET URL to download a file submission.

    Allowed for the student who submitted it and for instructors/admins (who
    need to download it to grade). Text/link submissions have no file → 404.
    """
    sub = await db.get(Submission, submission_id)
    if sub is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Submission not found")

    is_staff = user.role in (UserRole.INSTRUCTOR, UserRole.ADMIN)
    if not is_staff and sub.user_id != user.id:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "You cannot access this submission"
        )

    if not sub.content.startswith(_FILE_PREFIX):
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, "This submission has no uploaded file"
        )

    if not is_configured():
        raise HTTPException(
            status.HTTP_501_NOT_IMPLEMENTED, "File storage not configured"
        )

    return FileUrlOut(url=presign_get(sub.content))


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
    return sub
