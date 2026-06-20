"""Lecture notes — materials an instructor posts for a session.

`url` is a link to the material (drive/doc/slides/recording-notes). File upload
to object storage (R2) lands with the storage layer; kept URL-based for now to
avoid an untested/faked storage path.
"""

import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class NoteKind(str, enum.Enum):
    LINK = "LINK"
    PDF = "PDF"
    SLIDES = "SLIDES"
    SUMMARY = "SUMMARY"


class LectureNote(Base):
    __tablename__ = "lecture_notes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    session_id: Mapped[str] = mapped_column(
        ForeignKey("class_sessions.id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str] = mapped_column(String(200))
    url: Mapped[str] = mapped_column(Text)
    kind: Mapped[NoteKind] = mapped_column(
        SAEnum(NoteKind, name="note_kind"), default=NoteKind.LINK, nullable=False
    )
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
