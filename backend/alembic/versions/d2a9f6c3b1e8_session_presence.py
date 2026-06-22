"""session_presence (socket-observed attendance)

Revision ID: d2a9f6c3b1e8
Revises: c1f4a8b2e5d7
Create Date: 2026-06-22 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd2a9f6c3b1e8'
down_revision: Union[str, None] = 'c1f4a8b2e5d7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'session_presence',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('session_id', sa.String(length=36), nullable=False),
        sa.Column('user_id', sa.String(length=36), nullable=False),
        sa.Column(
            'joined_at',
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column('left_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        'ix_session_presence_session_id', 'session_presence', ['session_id']
    )
    op.create_index('ix_session_presence_user_id', 'session_presence', ['user_id'])


def downgrade() -> None:
    op.drop_index('ix_session_presence_user_id', table_name='session_presence')
    op.drop_index('ix_session_presence_session_id', table_name='session_presence')
    op.drop_table('session_presence')
