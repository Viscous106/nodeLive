"""Assignment + submission schemas."""

from datetime import datetime

from app.models.assignment import SubmissionStatus
from app.schemas.auth import CamelModel


class AssignmentCreate(CamelModel):
    course_id: str
    session_id: str | None = None
    title: str
    description: str | None = None
    due_at: datetime | None = None
    max_points: int = 100


class AssignmentOut(CamelModel):
    id: str
    course_id: str
    session_id: str | None = None
    title: str
    description: str | None = None
    due_at: datetime | None = None
    max_points: int
    unlocked_at: datetime | None = None


class SubmissionCreate(CamelModel):
    content: str


class SubmissionGrade(CamelModel):
    grade: int
    feedback: str | None = None


class SubmissionOut(CamelModel):
    id: str
    assignment_id: str
    user_id: str
    content: str
    status: SubmissionStatus
    grade: int | None = None
    feedback: str | None = None
