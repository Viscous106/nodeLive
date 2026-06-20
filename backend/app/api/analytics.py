"""Instructor session analytics — engagement from the live quiz/poll/leaderboard
tables. Attendance heatmap + completion rates are deferred until Dev B's
watch-tracking read-models land (no faking).
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import get_current_user
from app.db.session import get_db
from app.models.course import ClassSession, Enrollment
from app.models.live_meeting import (
    LeaderboardPoint,
    Poll,
    PollResponse,
    Quiz,
    QuizQuestion,
    QuizResponse,
)
from app.models.user import User, UserRole
from app.schemas.live import RankedUser

router = APIRouter(tags=["analytics"])


@router.get("/sessions/{session_id}/analytics")
async def session_analytics(
    session_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    cs = await db.get(ClassSession, session_id)
    if cs is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Session not found")
    if not (
        user.role in (UserRole.INSTRUCTOR, UserRole.ADMIN) or user.id == cs.host_id
    ):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Instructor only")

    enrolled = await db.scalar(
        select(func.count())
        .select_from(Enrollment)
        .where(Enrollment.course_id == cs.course_id)
    )

    question_ids = select(QuizQuestion.id).where(
        QuizQuestion.quiz_id.in_(select(Quiz.id).where(Quiz.session_id == session_id))
    )
    quiz_responses = await db.scalar(
        select(func.count())
        .select_from(QuizResponse)
        .where(QuizResponse.question_id.in_(question_ids))
    )
    quiz_participants = await db.scalar(
        select(func.count(func.distinct(QuizResponse.user_id)))
        .select_from(QuizResponse)
        .where(QuizResponse.question_id.in_(question_ids))
    )
    avg_points = await db.scalar(
        select(func.coalesce(func.avg(QuizResponse.points), 0))
        .select_from(QuizResponse)
        .where(QuizResponse.question_id.in_(question_ids))
    )

    poll_responses = await db.scalar(
        select(func.count())
        .select_from(PollResponse)
        .where(
            PollResponse.poll_id.in_(
                select(Poll.id).where(Poll.session_id == session_id)
            )
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
            .limit(5)
        )
    ).all()
    top_scorers = [
        RankedUser(
            user_id=r.user_id, display_name=r.display_name, points=int(r.pts)
        ).model_dump(by_alias=True)
        for r in rows
    ]

    return {
        "enrolled": int(enrolled or 0),
        "quizParticipants": int(quiz_participants or 0),
        "quizResponses": int(quiz_responses or 0),
        "pollResponses": int(poll_responses or 0),
        "avgQuizPoints": round(float(avg_points or 0)),
        "topScorers": top_scorers,
    }
