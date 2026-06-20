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


class ClassSessionCreate(CamelModel):
    course_id: str
    host_id: str | None = None  # admin can assign a different instructor as host
    title: str
    description: str | None = None
    scheduled_at: datetime
    duration_mins: int = 60
    zoom_meeting_id: str | None = None


class ClassSessionPatch(CamelModel):
    title: str | None = None
    description: str | None = None
    scheduled_at: datetime | None = None
    duration_mins: int | None = None
    zoom_meeting_id: str | None = None
    status: SessionStatus | None = None
