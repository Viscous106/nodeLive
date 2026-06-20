"""Lecture-note routes — instructor posts session materials; members view them."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import get_current_user
from app.db.session import get_db
from app.models.course import ClassSession, Enrollment
from app.models.lecture_note import LectureNote
from app.models.user import User, UserRole
from app.schemas.notes import NoteCreate, NoteOut

router = APIRouter(tags=["notes"])


async def _session_or_404(db: AsyncSession, session_id: str) -> ClassSession:
    cs = await db.get(ClassSession, session_id)
    if cs is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Session not found")
    return cs


def _is_staff(user: User, cs: ClassSession) -> bool:
    return user.role in (UserRole.INSTRUCTOR, UserRole.ADMIN) or user.id == cs.host_id


@router.post(
    "/sessions/{session_id}/notes",
    response_model=NoteOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_note(
    session_id: str,
    body: NoteCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> LectureNote:
    cs = await _session_or_404(db, session_id)
    if not _is_staff(user, cs):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Instructor only")
    note = LectureNote(
        session_id=session_id,
        title=body.title,
        url=body.url,
        kind=body.kind,
        created_by=user.id,
    )
    db.add(note)
    await db.commit()
    await db.refresh(note)
    return note


@router.get("/sessions/{session_id}/notes", response_model=list[NoteOut])
async def list_notes(
    session_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[LectureNote]:
    cs = await _session_or_404(db, session_id)
    if not _is_staff(user, cs):
        enrolled = await db.scalar(
            select(Enrollment).where(
                Enrollment.user_id == user.id, Enrollment.course_id == cs.course_id
            )
        )
        if enrolled is None:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN, "Not enrolled in this course"
            )
    return list(
        await db.scalars(
            select(LectureNote)
            .where(LectureNote.session_id == session_id)
            .order_by(LectureNote.created_at)
        )
    )
