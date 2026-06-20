"""quiz launched_at

Revision ID: a1f7c2b4e9d3
Revises: 3a0dd075c00f
Create Date: 2026-06-20 12:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1f7c2b4e9d3'
down_revision: Union[str, None] = '3a0dd075c00f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'quizzes',
        sa.Column('launched_at', sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('quizzes', 'launched_at')
