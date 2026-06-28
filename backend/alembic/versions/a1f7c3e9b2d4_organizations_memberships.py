"""organizations, memberships, invitations (expand-contract foundation)

Additive: creates the org/membership/invitation tables, inserts a single
default org, and backfills a membership per existing user from `users.role`.
`users.role` is intentionally KEPT as a synced mirror — dropped later in a
separate contract migration.

Revision ID: a1f7c3e9b2d4
Revises: 38cd957100b4
Create Date: 2026-06-20 17:10:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "a1f7c3e9b2d4"
down_revision: Union[str, None] = "38cd957100b4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# `user_role` already exists (owned by the users table) — reference it, never
# re-create it. `invitation_status` is new and created with the invitations table.
_USER_ROLE = postgresql.ENUM(
    "STUDENT", "INSTRUCTOR", "ADMIN", name="user_role", create_type=False
)

_DEFAULT_ORG_ID = "00000000-0000-0000-0000-0000000000af"


def upgrade() -> None:
    op.create_table(
        "organizations",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("slug", sa.String(length=80), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_organizations_slug"), "organizations", ["slug"], unique=True
    )

    op.create_table(
        "memberships",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("org_id", sa.String(length=36), nullable=False),
        sa.Column("role", _USER_ROLE, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "org_id", name="uq_membership_user_org"),
    )
    op.create_index(
        op.f("ix_memberships_user_id"), "memberships", ["user_id"], unique=False
    )
    op.create_index(
        op.f("ix_memberships_org_id"), "memberships", ["org_id"], unique=False
    )

    op.create_table(
        "invitations",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("org_id", sa.String(length=36), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("role", _USER_ROLE, nullable=False),
        sa.Column("token", sa.String(length=64), nullable=False),
        sa.Column(
            "status",
            sa.Enum("PENDING", "ACCEPTED", "REVOKED", name="invitation_status"),
            nullable=False,
        ),
        sa.Column("invited_by", sa.String(length=36), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["invited_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_invitations_org_id"), "invitations", ["org_id"], unique=False
    )
    op.create_index(
        op.f("ix_invitations_email"), "invitations", ["email"], unique=False
    )
    op.create_index(
        op.f("ix_invitations_token"), "invitations", ["token"], unique=True
    )

    # Insert the single default org and backfill a membership per user from the
    # `users.role` mirror (which is retained).
    op.execute(
        sa.text(
            "INSERT INTO organizations (id, name, slug, created_at) "
            "VALUES (:id, 'nodeLive', 'default', now())"
        ).bindparams(id=_DEFAULT_ORG_ID)
    )
    op.execute(
        sa.text(
            "INSERT INTO memberships (id, user_id, org_id, role, created_at) "
            "SELECT gen_random_uuid()::text, u.id, :org, u.role, now() FROM users u"
        ).bindparams(org=_DEFAULT_ORG_ID)
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_invitations_token"), table_name="invitations")
    op.drop_index(op.f("ix_invitations_email"), table_name="invitations")
    op.drop_index(op.f("ix_invitations_org_id"), table_name="invitations")
    op.drop_table("invitations")
    op.drop_index(op.f("ix_memberships_org_id"), table_name="memberships")
    op.drop_index(op.f("ix_memberships_user_id"), table_name="memberships")
    op.drop_table("memberships")
    op.drop_index(op.f("ix_organizations_slug"), table_name="organizations")
    op.drop_table("organizations")
    # Drop only the type we created here; `user_role` is owned by the users table.
    op.execute("DROP TYPE IF EXISTS invitation_status")
