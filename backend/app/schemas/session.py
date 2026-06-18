"""ClassSession schemas — the shared contract with the live-meeting side."""

from datetime import datetime

from app.models.course import SessionStatus
from app.schemas.auth import CamelModel


class ClassSessionOut(CamelModel):
    id: str
    course_id: str
    host_id: str
    title: str
    description: str | None = None
    scheduled_at: datetime
    duration_mins: int
    zoom_meeting_id: str | None = None
    status: SessionStatus


class ClassSessionPatch(CamelModel):
    status: SessionStatus | None = None
