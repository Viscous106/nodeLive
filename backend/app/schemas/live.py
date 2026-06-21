"""Live-meeting schemas."""

from datetime import datetime

from pydantic import Field

from app.models.live_meeting import PollStatus, QuizStatus
from app.schemas.auth import CamelModel


class ZoomJoinOut(CamelModel):
    signature: str
    sdk_key: str
    zoom_meeting_id: str
    password: str = ""  # meeting passcode (from Zoom when auto-created)
    zak: str = ""  # host token — lets an instructor START the meeting via the SDK


class CueCardCreate(CamelModel):
    content: str = Field(min_length=1)
    display_order: int = 0


class CueCardOut(CamelModel):
    id: str
    content: str
    display_order: int
    shown_at: datetime | None = None


class PollCreate(CamelModel):
    question: str = Field(min_length=1, max_length=500)
    options: list[str] = Field(min_length=2)


class PollOut(CamelModel):
    id: str
    question: str
    options: list[str]
    status: PollStatus


class PollOptionResult(CamelModel):
    option_index: int
    count: int
    pct: int


class PollResultsOut(CamelModel):
    poll_id: str
    status: PollStatus
    results: list[PollOptionResult]


class PollRespondIn(CamelModel):
    option_index: int = Field(ge=0)


class QuizQuestionIn(CamelModel):
    text: str = Field(min_length=1)
    options: list[str] = Field(min_length=2)
    correct_index: int = Field(ge=0)


class QuizCreate(CamelModel):
    title: str = Field(min_length=1, max_length=200)
    time_limit_secs: int = Field(default=30, ge=5, le=600)
    questions: list[QuizQuestionIn] = Field(min_length=1)


class QuizOut(CamelModel):
    id: str
    title: str
    time_limit_secs: int
    status: QuizStatus


class QuizRespondIn(CamelModel):
    question_id: str
    selected_index: int = Field(ge=0)


class QuizScoreOut(CamelModel):
    question_id: str
    correct: bool
    points: int
    correct_index: int


class QuizQuestionResult(CamelModel):
    question_id: str
    text: str
    correct_index: int
    response_count: int


class QuizResultsOut(CamelModel):
    quiz_id: str
    status: QuizStatus
    questions: list[QuizQuestionResult]


class NoticeCreate(CamelModel):
    content: str = Field(min_length=1)
    priority: str = "NORMAL"


class PinnedMessageIn(CamelModel):
    message: str = Field(min_length=1)


class BookmarkCreate(CamelModel):
    timestamp_ms: int = Field(ge=0)
    label: str | None = None


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
