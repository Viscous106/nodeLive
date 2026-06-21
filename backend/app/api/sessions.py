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

from app.auth.deps import get_current_user, require_role
from app.db.session import get_db
from app.models.course import ClassSession, Course, Enrollment, SessionStatus
from app.models.user import User, UserRole
from app.schemas.session import (
    ClassSessionCreate,
    ClassSessionOut,
    ClassSessionPatch,
)
from app.services.enrollment import enroll_all_users

router = APIRouter(prefix="/sessions", tags=["sessions"])

_privileged = require_role(UserRole.INSTRUCTOR, UserRole.ADMIN)


def _enrolled_course_ids(user_id: str):
    return select(Enrollment.course_id).where(Enrollment.user_id == user_id)


@router.post("", response_model=ClassSessionOut, status_code=status.HTTP_201_CREATED)
async def create_session(
    body: ClassSessionCreate,
    user: User = Depends(_privileged),
    db: AsyncSession = Depends(get_db),
) -> ClassSession:
    """Schedule a class session. Instructor/admin only; the creator is the host.

    v1 takes a manually-entered `zoomMeetingId`; auto-creating a real Zoom
    meeting via S2S is a documented fast-follow.
    """
    if await db.get(Course, body.course_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Course not found")

    # The scheduler (admin/instructor) may hand the host role to ANY member —
    # an instructor, another admin, or a student presenter. That person becomes
    # `host_id`, and ONLY they are the Zoom host (the single ZAK holder who can
    # start the meeting); everyone else joins as a named participant.
    host_id = user.id
    if body.host_id and user.role in (UserRole.ADMIN, UserRole.INSTRUCTOR):
        host = await db.get(User, body.host_id)
        if host is None:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY, "Host user not found"
            )
        host_id = body.host_id

    cs = ClassSession(
        course_id=body.course_id,
        host_id=host_id,
        title=body.title,
        description=body.description,
        scheduled_at=body.scheduled_at,
        duration_mins=body.duration_mins,
        zoom_meeting_id=body.zoom_meeting_id,
        status=SessionStatus.SCHEDULED,
    )
    db.add(cs)
    # Single-org: scheduling a class enrolls every current member into its
    # course, so it shows on everyone's dashboard (and legacy courses get
    # backfilled the moment a new session is scheduled).
    await enroll_all_users(db, body.course_id)
    await db.commit()
    await db.refresh(cs)
    return cs


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


@router.get("/{session_id}/similar", response_model=list[ClassSessionOut])
async def similar_sessions(
    session_id: str,
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[ClassSession]:
    target = await _get_or_404(db, session_id)
    stmt = (
        select(ClassSession)
        .where(
            ClassSession.course_id == target.course_id,
            ClassSession.id != target.id,
        )
        .order_by(ClassSession.scheduled_at.desc())
        .limit(5)
    )
    return list(await db.scalars(stmt))


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
