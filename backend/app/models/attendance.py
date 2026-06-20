"""Attendance models — the durable + authoritative layers of the three-layer
attendance truth model (ported from `testing/lib/db.js`).

- `Meeting`           — one row per Zoom occurrence (zoom_uuid ↔ numeric id).
- `AttendanceSession` — raw participant join/leave spans (webhook = durable log;
                        report = post-meeting fill). Reconnects appear as
                        multiple rows; the union is computed at reconcile time.
- `AttendanceFinal`   — the authoritative per-user present time, recomputed from
                        the Reports API as the union of intervals (the tie-breaker).
- `WebhookEvent`      — idempotency ledger; Zoom redelivers, so each event is
                        claimed exactly once.

These ingest external truth, so identity columns are plain strings (no FKs):
`user_id` is the Zoom `customer_key` (our app user id, absent for guests) and
`email` is the fallback match key.
"""

import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    JSON,
    DateTime,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class AttendanceSource(str, enum.Enum):
    WEBHOOK = "webhook"
    REPORT = "report"


class Meeting(Base):
    __tablename__ = "meetings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    # Per-occurrence UUID (recurring meetings reuse the numeric id). May contain
    # '/' — kept verbatim; Reports API calls double-encode it.
    zoom_uuid: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    zoom_meeting_id: Mapped[str | None] = mapped_column(
        String(64), nullable=True, index=True
    )
    host_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    topic: Mapped[str | None] = mapped_column(String(500), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    ended_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class AttendanceSession(Base):
    __tablename__ = "attendance_sessions"
    __table_args__ = (
        UniqueConstraint(
            "zoom_uuid",
            "zoom_participant_uuid",
            name="uq_attendance_session_participant",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    zoom_uuid: Mapped[str] = mapped_column(String(255), index=True)
    zoom_participant_uuid: Mapped[str] = mapped_column(String(255))
    user_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    display_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    joined_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    left_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    source: Mapped[str] = mapped_column(
        String(16), default=AttendanceSource.WEBHOOK.value, nullable=False
    )


class AttendanceFinal(Base):
    __tablename__ = "attendance_final"
    __table_args__ = (
        UniqueConstraint(
            "zoom_uuid", "user_id", "email", name="uq_attendance_final_identity"
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    zoom_uuid: Mapped[str] = mapped_column(String(255), index=True)
    user_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    display_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    present_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    # Merged [start, end] spans (epoch seconds), for audit/debug.
    sessions: Mapped[list] = mapped_column(JSON, default=list)
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class WebhookEvent(Base):
    __tablename__ = "webhook_events"

    event_id: Mapped[str] = mapped_column(Text, primary_key=True)
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
