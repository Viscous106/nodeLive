"""Session routes.

List/timetable feed the dashboard; GET/PATCH /:id are the contract consumed by
the live-meeting side. Collection routes (`""`, `/this-week`) are declared
before `/{session_id}` so a literal path isn't swallowed as an id.
"""

from datetime import UTC, datetime, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import get_current_user
from app.db.session import get_db
from app.models.course import ClassSession, Enrollment, SessionStatus
from app.models.user import User, UserRole
from app.schemas.session import ClassSessionOut, ClassSessionPatch

router = APIRouter(prefix="/sessions", tags=["sessions"])


def _enrolled_course_ids(user_id: str):
    return select(Enrollment.course_id).where(Enrollment.user_id == user_id)


@router.get("", response_model=list[ClassSessionOut])
async def list_sessions(
    status: Literal["upcoming", "past"] | None = None,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[ClassSession]:
    stmt = select(ClassSession).where(
        ClassSession.course_id.in_(_enrolled_course_ids(user.id))
    )
    now = datetime.now(UTC)
    if status == "upcoming":
        stmt = stmt.where(
            ClassSession.scheduled_at >= now,
            ClassSession.status.notin_([SessionStatus.ENDED, SessionStatus.CANCELLED]),
        ).order_by(ClassSession.scheduled_at)
    elif status == "past":
        stmt = stmt.where(
            or_(
                ClassSession.scheduled_at < now,
                ClassSession.status == SessionStatus.ENDED,
            )
        ).order_by(ClassSession.scheduled_at.desc())
    else:
        stmt = stmt.order_by(ClassSession.scheduled_at)
    return list(await db.scalars(stmt))


@router.get("/this-week", response_model=list[ClassSessionOut])
async def sessions_this_week(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[ClassSession]:
    start = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=7)
    stmt = (
        select(ClassSession)
        .where(
            ClassSession.course_id.in_(_enrolled_course_ids(user.id)),
            ClassSession.scheduled_at >= start,
            ClassSession.scheduled_at < end,
        )
        .order_by(ClassSession.scheduled_at)
    )
    return list(await db.scalars(stmt))


async def _get_or_404(db: AsyncSession, session_id: str) -> ClassSession:
    cs = await db.get(ClassSession, session_id)
    if cs is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Session not found"
        )
    return cs


@router.get("/{session_id}", response_model=ClassSessionOut)
async def get_session(
    session_id: str,
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ClassSession:
    return await _get_or_404(db, session_id)


@router.patch("/{session_id}", response_model=ClassSessionOut)
async def patch_session(
    session_id: str,
    body: ClassSessionPatch,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ClassSession:
    cs = await _get_or_404(db, session_id)

    is_privileged = user.role in (UserRole.INSTRUCTOR, UserRole.ADMIN)
    if user.id != cs.host_id and not is_privileged:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the host or an instructor can modify this session",
        )

    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(cs, field, value)
    await db.commit()
    await db.refresh(cs)
    return cs
