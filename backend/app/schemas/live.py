"""Live-meeting schemas."""

from datetime import datetime

from app.models.live_meeting import PollStatus, QuizStatus
from app.schemas.auth import CamelModel


class ZoomJoinOut(CamelModel):
    signature: str
    sdk_key: str
    zoom_meeting_id: str


class CueCardOut(CamelModel):
    id: str
    content: str
    display_order: int
    shown_at: datetime | None = None


class PollOut(CamelModel):
    id: str
    question: str
    options: list[str]
    status: PollStatus


class QuizOut(CamelModel):
    id: str
    title: str
    time_limit_secs: int
    status: QuizStatus


class NoticeOut(CamelModel):
    id: str
    content: str
    priority: str
    created_at: datetime
    expires_at: datetime | None = None


class BookmarkOut(CamelModel):
    id: str
    timestamp_ms: int
    label: str | None = None
    created_at: datetime


class RankedUser(CamelModel):
    user_id: str
    display_name: str
    points: int


class LiveStateOut(CamelModel):
    current_cue_card: CueCardOut | None = None
    active_poll: PollOut | None = None
    active_quiz: QuizOut | None = None
    pinned_message: str | None = None
    recent_notices: list[NoticeOut] = []
    user_bookmarks: list[BookmarkOut] = []
    my_quiz_score: int = 0
    leaderboard: list[RankedUser] = []
