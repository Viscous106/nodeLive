"""Model registry.

Import every model module here so `Base.metadata` is fully populated for
Alembic autogenerate. Dev A and Dev B add their model imports as they build
(e.g. `from app.models.user import User`).
"""

from app.models.base import Base

__all__ = ["Base"]
