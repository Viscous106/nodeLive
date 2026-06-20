"""Model registry.

Import every model module here so `Base.metadata` is fully populated for
Alembic autogenerate. Dev A and Dev B add their model imports as they build.
"""

from app.models.assignment import Assignment, Submission, SubmissionStatus
from app.models.attendance import (
    AttendanceFinal,
    AttendanceSession,
    AttendanceSource,
    Meeting,
    WebhookEvent,
)
from app.models.base import Base
from app.models.course import ClassSession, Course, Enrollment, SessionStatus
from app.models.lecture_note import LectureNote, NoteKind
from app.models.live_meeting import (
    Bookmark,
    CueCard,
    LeaderboardPoint,
    Notice,
    PinnedMessage,
    Poll,
    PollResponse,
    PollStatus,
    Quiz,
    QuizQuestion,
    QuizResponse,
    QuizStatus,
)
from app.models.user import User, UserRole

__all__ = [
    "Base",
    "User",
    "UserRole",
    "Course",
    "ClassSession",
    "SessionStatus",
    "Enrollment",
    "Assignment",
    "Submission",
    "SubmissionStatus",
    "CueCard",
    "Poll",
    "PollResponse",
    "PollStatus",
    "Quiz",
    "QuizQuestion",
    "QuizResponse",
    "QuizStatus",
    "Bookmark",
    "Notice",
    "PinnedMessage",
    "LeaderboardPoint",
    "Meeting",
    "AttendanceSession",
    "AttendanceFinal",
    "AttendanceSource",
    "WebhookEvent",
    "LectureNote",
    "NoteKind",
]
