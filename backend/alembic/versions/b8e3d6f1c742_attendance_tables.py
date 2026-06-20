"""attendance tables (meetings, attendance_sessions, attendance_final, webhook_events)

Revision ID: b8e3d6f1c742
Revises: a1f7c2b4e9d3
Create Date: 2026-06-20 13:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b8e3d6f1c742'
down_revision: Union[str, None] = 'a1f7c2b4e9d3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'meetings',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('zoom_uuid', sa.String(length=255), nullable=False),
        sa.Column('zoom_meeting_id', sa.String(length=64), nullable=True),
        sa.Column('host_id', sa.String(length=255), nullable=True),
        sa.Column('topic', sa.String(length=500), nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('ended_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_meetings_zoom_uuid'), 'meetings', ['zoom_uuid'], unique=True)
    op.create_index(op.f('ix_meetings_zoom_meeting_id'), 'meetings', ['zoom_meeting_id'], unique=False)

    op.create_table(
        'attendance_sessions',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('zoom_uuid', sa.String(length=255), nullable=False),
        sa.Column('zoom_participant_uuid', sa.String(length=255), nullable=False),
        sa.Column('user_id', sa.String(length=36), nullable=True),
        sa.Column('email', sa.String(length=255), nullable=True),
        sa.Column('display_name', sa.String(length=255), nullable=True),
        sa.Column('joined_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('left_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('source', sa.String(length=16), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('zoom_uuid', 'zoom_participant_uuid', name='uq_attendance_session_participant'),
    )
    op.create_index(op.f('ix_attendance_sessions_zoom_uuid'), 'attendance_sessions', ['zoom_uuid'], unique=False)

    op.create_table(
        'attendance_final',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('zoom_uuid', sa.String(length=255), nullable=False),
        sa.Column('user_id', sa.String(length=36), nullable=True),
        sa.Column('email', sa.String(length=255), nullable=True),
        sa.Column('display_name', sa.String(length=255), nullable=True),
        sa.Column('present_seconds', sa.Integer(), nullable=False),
        sa.Column('sessions', sa.JSON(), nullable=True),
        sa.Column('computed_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('zoom_uuid', 'user_id', 'email', name='uq_attendance_final_identity'),
    )
    op.create_index(op.f('ix_attendance_final_zoom_uuid'), 'attendance_final', ['zoom_uuid'], unique=False)

    op.create_table(
        'webhook_events',
        sa.Column('event_id', sa.Text(), nullable=False),
        sa.Column('received_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('event_id'),
    )


def downgrade() -> None:
    op.drop_table('webhook_events')
    op.drop_index(op.f('ix_attendance_final_zoom_uuid'), table_name='attendance_final')
    op.drop_table('attendance_final')
    op.drop_index(op.f('ix_attendance_sessions_zoom_uuid'), table_name='attendance_sessions')
    op.drop_table('attendance_sessions')
    op.drop_index(op.f('ix_meetings_zoom_meeting_id'), table_name='meetings')
    op.drop_index(op.f('ix_meetings_zoom_uuid'), table_name='meetings')
    op.drop_table('meetings')
