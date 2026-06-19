"""Course schemas."""

from app.schemas.auth import CamelModel


class CourseOut(CamelModel):
    id: str
    title: str
