"""class_sessions ended_at

Revision ID: c1f4a8b2e5d7
Revises: rec0watch7m7a
Create Date: 2026-06-21 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c1f4a8b2e5d7'
down_revision: Union[str, None] = 'rec0watch7m7a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'class_sessions',
        sa.Column('ended_at', sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('class_sessions', 'ended_at')
