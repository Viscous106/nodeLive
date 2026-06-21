"""Student progress response schemas."""

from datetime import datetime

from app.models.assignment import SubmissionStatus
from app.models.course import SessionStatus
from app.schemas.auth import CamelModel


class AssignmentProgressItem(CamelModel):
    id: str
    title: str
    max_points: int
    due_at: datetime | None = None
    status: SubmissionStatus | None = None
    grade: int | None = None
    feedback: str | None = None
    submitted_at: datetime | None = None


class SessionProgressItem(CamelModel):
    id: str
    title: str
    session_status: SessionStatus
    scheduled_at: datetime
    watch_percent: float | None = None


class CourseProgressItem(CamelModel):
    id: str
    title: str
    assignments: list[AssignmentProgressItem]
    sessions: list[SessionProgressItem]


class ProgressOut(CamelModel):
    courses: list[CourseProgressItem]
    assignments_total: int
    assignments_submitted: int
    assignments_graded: int
    avg_grade: float | None = None
