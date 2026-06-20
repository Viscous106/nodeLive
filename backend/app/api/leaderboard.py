"""Global leaderboard — total quiz/poll points per user across all sessions.

Reads the live-meeting LeaderboardPoint table (written by Dev B's quiz engine);
this is the dashboard-side surface for the drawer's Leaderboard nav.
"""

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import get_current_user
from app.db.session import get_db
from app.models.live_meeting import LeaderboardPoint
from app.models.user import User
from app.schemas.live import RankedUser

router = APIRouter(tags=["leaderboard"])


@router.get("/leaderboard", response_model=list[RankedUser])
async def global_leaderboard(
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[RankedUser]:
    pts = func.sum(LeaderboardPoint.points).label("pts")
    rows = (
        await db.execute(
            select(LeaderboardPoint.user_id, User.display_name, pts)
            .join(User, User.id == LeaderboardPoint.user_id)
            .group_by(LeaderboardPoint.user_id, User.display_name)
            .order_by(pts.desc())
            .limit(20)
        )
    ).all()
    return [
        RankedUser(user_id=r.user_id, display_name=r.display_name, points=int(r.pts))
        for r in rows
    ]
