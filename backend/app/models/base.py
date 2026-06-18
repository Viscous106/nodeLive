"""Declarative base for all SQLAlchemy models.

Every model inherits from `Base`. `AsyncAttrs` enables `await obj.awaitable_attrs.x`
for lazy relationship loading in async code. Model modules (user.py, course.py,
live_meeting.py, ...) are imported in `app.models.__init__` so Alembic autogenerate
sees the full metadata.
"""

from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlalchemy.orm import DeclarativeBase


class Base(AsyncAttrs, DeclarativeBase):
    pass
