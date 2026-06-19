"""Live-meeting API (Dev B).

M1: issue a Zoom Meeting SDK signature to join a session. Hosts/instructors get
role 1; enrolled students get role 0; everyone else is refused.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import get_current_user
from app.core.config import settings
from app.db.session import get_db
from app.models.course import ClassSession, Enrollment
from app.models.user import User, UserRole
from app.schemas.live import ZoomJoinOut
from app.utils.zoom_jwt import generate_zoom_signature

router = APIRouter(tags=["live"])


@router.post("/sessions/{session_id}/join", response_model=ZoomJoinOut)
async def join(
    session_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ZoomJoinOut:
    cs = await db.get(ClassSession, session_id)
    if cs is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Session not found")
    if not cs.zoom_meeting_id:
        raise HTTPException(status.HTTP_409_CONFLICT, "Session has no Zoom meeting yet")

    is_host = user.id == cs.host_id or user.role in (
        UserRole.INSTRUCTOR,
        UserRole.ADMIN,
    )
    if not is_host:
        enrolled = await db.scalar(
            select(Enrollment).where(
                Enrollment.user_id == user.id,
                Enrollment.course_id == cs.course_id,
            )
        )
        if enrolled is None:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN, "You are not enrolled in this course"
            )

    role = 1 if is_host else 0
    signature = generate_zoom_signature(
        settings.ZOOM_SDK_KEY,
        settings.ZOOM_SDK_SECRET,
        cs.zoom_meeting_id,
        role,
    )
    return ZoomJoinOut(
        signature=signature,
        sdk_key=settings.ZOOM_SDK_KEY,
        zoom_meeting_id=cs.zoom_meeting_id,
    )
