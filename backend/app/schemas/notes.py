"""Lecture note schemas."""

from datetime import datetime

from app.models.lecture_note import NoteKind
from app.schemas.auth import CamelModel


class NoteCreate(CamelModel):
    title: str
    url: str
    kind: NoteKind = NoteKind.LINK


class NoteOut(CamelModel):
    id: str
    title: str
    url: str
    kind: NoteKind
    created_at: datetime
