"""Live-meeting API (Dev B).

M1: issue a Zoom Meeting SDK signature to join a session. Hosts/instructors get
role 1; enrolled students get role 0; everyone else is refused.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import get_current_user
from app.core.config import settings
from app.db.session import get_db
from app.models.course import ClassSession, Enrollment
from app.models.live_meeting import (
    Bookmark,
    CueCard,
    LeaderboardPoint,
    Notice,
    PinnedMessage,
    Poll,
    PollStatus,
    Quiz,
    QuizStatus,
)
from app.models.user import User, UserRole
from app.schemas.live import LiveStateOut, RankedUser, ZoomJoinOut
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


@router.get("/sessions/{session_id}/live/state", response_model=LiveStateOut)
async def live_state(
    session_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> LiveStateOut:
    """Full current state for a client (re)joining the meeting."""
    cs = await db.get(ClassSession, session_id)
    if cs is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Session not found")

    current_cue = await db.scalar(
        select(CueCard)
        .where(CueCard.session_id == session_id, CueCard.shown_at.is_not(None))
        .order_by(CueCard.shown_at.desc())
        .limit(1)
    )
    active_poll = await db.scalar(
        select(Poll)
        .where(Poll.session_id == session_id, Poll.status == PollStatus.OPEN)
        .order_by(Poll.created_at.desc())
        .limit(1)
    )
    active_quiz = await db.scalar(
        select(Quiz)
        .where(Quiz.session_id == session_id, Quiz.status == QuizStatus.LIVE)
        .order_by(Quiz.created_at.desc())
        .limit(1)
    )
    pinned = await db.scalar(
        select(PinnedMessage).where(PinnedMessage.session_id == session_id)
    )
    notices = list(
        await db.scalars(
            select(Notice)
            .where(Notice.session_id == session_id)
            .order_by(Notice.created_at.desc())
            .limit(10)
        )
    )
    bookmarks = list(
        await db.scalars(
            select(Bookmark)
            .where(Bookmark.session_id == session_id, Bookmark.user_id == user.id)
            .order_by(Bookmark.timestamp_ms)
        )
    )
    my_score = await db.scalar(
        select(func.coalesce(func.sum(LeaderboardPoint.points), 0)).where(
            LeaderboardPoint.session_id == session_id,
            LeaderboardPoint.user_id == user.id,
        )
    )
    pts = func.sum(LeaderboardPoint.points).label("pts")
    rows = (
        await db.execute(
            select(LeaderboardPoint.user_id, User.display_name, pts)
            .join(User, User.id == LeaderboardPoint.user_id)
            .where(LeaderboardPoint.session_id == session_id)
            .group_by(LeaderboardPoint.user_id, User.display_name)
            .order_by(pts.desc())
            .limit(10)
        )
    ).all()
    leaderboard = [
        RankedUser(user_id=r.user_id, display_name=r.display_name, points=int(r.pts))
        for r in rows
    ]

    return LiveStateOut(
        current_cue_card=current_cue,
        active_poll=active_poll,
        active_quiz=active_quiz,
        pinned_message=(pinned.message if pinned else None),
        recent_notices=notices,
        user_bookmarks=bookmarks,
        my_quiz_score=int(my_score or 0),
        leaderboard=leaderboard,
    )
