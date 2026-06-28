# Organizations & Memberships (AF) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an org/membership identity layer and a clean role-assignment API (invite + promote), without breaking anything that reads `User.role`.

**Architecture:** Expand-contract. Add `Organization` / `Membership` / `Invitation`; backfill a membership per existing user from `users.role`; **keep `users.role` as a synced mirror** (every role write updates both). New `require_org_role` guard + admin endpoints read the membership; all existing guards/serializers/tests are untouched. A later (separate) contract step drops `users.role`.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2.0 async, Alembic, pytest-asyncio. Frontend untouched in this plan.

**Spec:** `docs/superpowers/specs/2026-06-20-admin-dashboard-design.md` (Part A + Members & Roles).

**Run tests with** (from `backend/`, venv active):
```bash
export TEST_DATABASE_URL="postgresql+asyncpg://viscous@localhost:5432/nodelive_test" \
  REDIS_URL="redis://localhost:6379/0" AUTH_SECRET=x ENVIRONMENT=test \
  ZOOM_SDK_KEY=k ZOOM_SDK_SECRET=s
```
The `conftest` builds the schema with `Base.metadata.create_all`, so new models are picked up automatically; the migration is verified separately (Task 2).

---

## File structure

- Create `backend/app/models/org.py` — `Organization`, `Membership`, `Invitation`, `InvitationStatus`.
- Modify `backend/app/models/__init__.py` — register the new models.
- Create `backend/alembic/versions/<rev>_organizations_memberships.py` — tables + default org + membership backfill (keeps `users.role`).
- Create `backend/app/services/orgs.py` — `DEFAULT_ORG_SLUG`, `get_default_org`, `ensure_membership`, `set_member_role` (the single role-write that syncs `users.role`).
- Modify `backend/app/auth/deps.py` — add `get_current_membership`, `require_org_role` (additive).
- Create `backend/app/schemas/org.py` — `MemberOut`, `RoleUpdate`, `InviteCreate`, `InvitationOut`, `InvitePreview`.
- Create `backend/app/api/org.py` — admin members/role/invitations + public invite preview.
- Modify `backend/app/main.py` — include the new router.
- Modify `backend/app/api/auth.py` — `signup` accepts `inviteToken`.
- Modify `backend/app/schemas/auth.py` — `SignupIn.invite_token`.
- Modify `backend/scripts/set_role.py` and `backend/scripts/seed.py` — write membership + mirror; seed makes the instructor an org ADMIN.
- Tests: `backend/tests/test_orgs_service.py`, `test_org_members.py`, `test_org_invitations.py`, `test_signup_invite.py`, `test_orgs_migration.py`.

---

## Task 1: Org/Membership/Invitation models

**Files:**
- Create: `backend/app/models/org.py`
- Modify: `backend/app/models/__init__.py`

- [ ] **Step 1: Write the models**

```python
# backend/app/models/org.py
"""Organizations & memberships (identity foundation).

`Membership` is the management surface and future source of truth for a user's
role within an org. During the expand-contract transition `users.role` is kept
as a synced mirror, so existing readers keep working.
"""

import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.user import UserRole


def _uuid() -> str:
    return str(uuid.uuid4())


class InvitationStatus(str, enum.Enum):
    PENDING = "PENDING"
    ACCEPTED = "ACCEPTED"
    REVOKED = "REVOKED"


class Organization(Base):
    __tablename__ = "organizations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(200))
    slug: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class Membership(Base):
    __tablename__ = "memberships"
    __table_args__ = (
        UniqueConstraint("user_id", "org_id", name="uq_membership_user_org"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    org_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    # Reuses the existing `user_role` enum type.
    role: Mapped[UserRole] = mapped_column(SAEnum(UserRole, name="user_role"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class Invitation(Base):
    __tablename__ = "invitations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    org_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    email: Mapped[str] = mapped_column(String(255), index=True)
    role: Mapped[UserRole] = mapped_column(SAEnum(UserRole, name="user_role"))
    token: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    status: Mapped[InvitationStatus] = mapped_column(
        SAEnum(InvitationStatus, name="invitation_status"),
        default=InvitationStatus.PENDING,
    )
    invited_by: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    accepted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
```

> Note: `SAEnum(UserRole, name="user_role")` reuses the existing enum **type** (no
> duplicate). `Text` import is unused — omit it; keep imports minimal.

- [ ] **Step 2: Register the models** in `backend/app/models/__init__.py` — add to the imports and `__all__`:

```python
from app.models.org import (
    Invitation,
    InvitationStatus,
    Membership,
    Organization,
)
```
Add `"Organization"`, `"Membership"`, `"Invitation"`, `"InvitationStatus"` to `__all__`.

- [ ] **Step 3: Verify import + metadata**

Run: `python -c "from app.models import Organization, Membership, Invitation; from app.models.base import Base; print('memberships' in Base.metadata.tables, 'invitations' in Base.metadata.tables)"`
Expected: `True True`

- [ ] **Step 4: Commit**

```bash
git add backend/app/models/org.py backend/app/models/__init__.py
git commit -m "feat(orgs): Organization/Membership/Invitation models"
```

---

## Task 2: Migration — tables + default org + membership backfill (keep users.role)

**Files:**
- Create: `backend/alembic/versions/c1a2b3d4e5f6_organizations_memberships.py`
- Test: `backend/tests/test_orgs_migration.py`

- [ ] **Step 1: Find the current head**

Run: `alembic heads`
Expected: one revision id (e.g. `b8e3d6f1c742`). Use it as `down_revision`.

- [ ] **Step 2: Write the migration** (set `down_revision` to the head from Step 1)

```python
"""organizations, memberships, invitations (+ membership backfill)

Revision ID: c1a2b3d4e5f6
Revises: <HEAD_FROM_STEP_1>
Create Date: 2026-06-20 14:00:00.000000
"""
import uuid
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "c1a2b3d4e5f6"
down_revision: Union[str, None] = "<HEAD_FROM_STEP_1>"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# The user_role PG enum already exists (created by the users table); reference it
# without re-creating it.
_user_role = sa.Enum("STUDENT", "INSTRUCTOR", "ADMIN", name="user_role", create_type=False)
_invite_status = sa.Enum("PENDING", "ACCEPTED", "REVOKED", name="invitation_status")


def upgrade() -> None:
    op.create_table(
        "organizations",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("slug", sa.String(length=100), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_organizations_slug"), "organizations", ["slug"], unique=True)

    op.create_table(
        "memberships",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("org_id", sa.String(length=36), nullable=False),
        sa.Column("role", _user_role, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "org_id", name="uq_membership_user_org"),
    )
    op.create_index(op.f("ix_memberships_user_id"), "memberships", ["user_id"], unique=False)
    op.create_index(op.f("ix_memberships_org_id"), "memberships", ["org_id"], unique=False)

    op.create_table(
        "invitations",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("org_id", sa.String(length=36), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("role", _user_role, nullable=False),
        sa.Column("token", sa.String(length=64), nullable=False),
        sa.Column("status", _invite_status, nullable=False),
        sa.Column("invited_by", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["invited_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_invitations_org_id"), "invitations", ["org_id"], unique=False)
    op.create_index(op.f("ix_invitations_email"), "invitations", ["email"], unique=False)
    op.create_index(op.f("ix_invitations_token"), "invitations", ["token"], unique=True)

    # Default org + backfill a membership per existing user from users.role.
    org_id = str(uuid.uuid4())
    op.execute(
        sa.text(
            "INSERT INTO organizations (id, name, slug, created_at) "
            "VALUES (:id, 'nodeLive', 'default', now())"
        ).bindparams(id=org_id)
    )
    op.execute(
        sa.text(
            "INSERT INTO memberships (id, user_id, org_id, role, created_at) "
            "SELECT gen_random_uuid()::text, u.id, :org_id, u.role, now() FROM users u"
        ).bindparams(org_id=org_id)
    )
    # users.role is intentionally KEPT (expand-contract mirror).


def downgrade() -> None:
    op.drop_index(op.f("ix_invitations_token"), table_name="invitations")
    op.drop_index(op.f("ix_invitations_email"), table_name="invitations")
    op.drop_index(op.f("ix_invitations_org_id"), table_name="invitations")
    op.drop_table("invitations")
    op.execute("DROP TYPE IF EXISTS invitation_status")
    op.drop_index(op.f("ix_memberships_org_id"), table_name="memberships")
    op.drop_index(op.f("ix_memberships_user_id"), table_name="memberships")
    op.drop_table("memberships")
    op.drop_index(op.f("ix_organizations_slug"), table_name="organizations")
    op.drop_table("organizations")
    # user_role enum is left in place (still used by users.role).
```

> `gen_random_uuid()` is built into Postgres 13+. The default org is created in
> the migration so the backfill has an `org_id`.

- [ ] **Step 3: Verify round-trip on a fresh DB** (create `backend/tests/test_orgs_migration.py` as a doc of the manual check, but run it by hand):

```bash
python -c "
import asyncio, asyncpg
async def m():
    a = await asyncpg.connect(host='localhost', user='viscous', database='postgres')
    await a.execute('DROP DATABASE IF EXISTS nodelive_mig'); await a.execute('CREATE DATABASE nodelive_mig'); await a.close()
asyncio.run(m())"
MIG="postgresql+asyncpg://viscous@localhost:5432/nodelive_mig"
DIRECT_DATABASE_URL=$MIG DATABASE_URL=$MIG alembic upgrade head
DIRECT_DATABASE_URL=$MIG DATABASE_URL=$MIG alembic downgrade -1
DIRECT_DATABASE_URL=$MIG DATABASE_URL=$MIG alembic upgrade head
```
Expected: each command prints the upgrade/downgrade lines with no error; the 3 tables exist after the final upgrade.

- [ ] **Step 4: Verify backfill keeps users.role and creates one membership per user**

```bash
DIRECT_DATABASE_URL=$MIG DATABASE_URL=$MIG python -c "
import asyncio, asyncpg
async def m():
    c = await asyncpg.connect(host='localhost', user='viscous', database='nodelive_mig')
    cols = await c.fetch(\"SELECT column_name FROM information_schema.columns WHERE table_name='users' AND column_name='role'\")
    print('users.role kept:', len(cols)==1)
    await c.close()
asyncio.run(m())"
```
Expected: `users.role kept: True`. Drop `nodelive_mig` afterward.

- [ ] **Step 5: Commit**

```bash
git add backend/alembic/versions/c1a2b3d4e5f6_organizations_memberships.py
git commit -m "feat(orgs): migration — org/membership/invitation tables + backfill (keep users.role)"
```

---

## Task 3: Role service (default org, membership, synced role write)

**Files:**
- Create: `backend/app/services/orgs.py`
- Create: `backend/app/services/__init__.py` (empty)
- Test: `backend/tests/test_orgs_service.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_orgs_service.py
from app.auth.security import hash_password
from app.models.org import Organization
from app.models.user import User, UserRole
from app.services.orgs import DEFAULT_ORG_SLUG, ensure_default_org, ensure_membership, set_member_role


async def _user(session, email, role="STUDENT"):
    u = User(email=email, hashed_password=hash_password("pw-123456"),
             display_name=email.split("@")[0], role=UserRole(role))
    session.add(u)
    await session.commit()
    return u


async def test_set_member_role_syncs_user_role_mirror(session):
    org = await ensure_default_org(session)
    assert org.slug == DEFAULT_ORG_SLUG
    user = await _user(session, "a@x.com", "STUDENT")
    await ensure_membership(session, user.id, org.id, UserRole.STUDENT)

    m = await set_member_role(session, user.id, UserRole.INSTRUCTOR)

    assert m.role is UserRole.INSTRUCTOR
    await session.refresh(user)
    assert user.role is UserRole.INSTRUCTOR  # mirror synced
```

- [ ] **Step 2: Run it to verify it fails**

Run: `python -m pytest tests/test_orgs_service.py -q`
Expected: FAIL — `ModuleNotFoundError: app.services.orgs`.

- [ ] **Step 3: Write the service**

```python
# backend/app/services/orgs.py
"""Org/membership helpers. Single-org for now; `set_member_role` is the one place
roles are written, keeping the `users.role` mirror in sync (expand-contract)."""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.org import Membership, Organization
from app.models.user import User, UserRole

DEFAULT_ORG_SLUG = "default"


async def ensure_default_org(db: AsyncSession) -> Organization:
    org = await db.scalar(select(Organization).where(Organization.slug == DEFAULT_ORG_SLUG))
    if org is None:
        org = Organization(name="nodeLive", slug=DEFAULT_ORG_SLUG)
        db.add(org)
        await db.commit()
        await db.refresh(org)
    return org


async def get_default_org(db: AsyncSession) -> Organization:
    org = await db.scalar(select(Organization).where(Organization.slug == DEFAULT_ORG_SLUG))
    if org is None:
        raise RuntimeError("default org missing — run the migration/seed")
    return org


async def ensure_membership(
    db: AsyncSession, user_id: str, org_id: str, role: UserRole
) -> Membership:
    m = await db.scalar(
        select(Membership).where(Membership.user_id == user_id, Membership.org_id == org_id)
    )
    if m is None:
        m = Membership(user_id=user_id, org_id=org_id, role=role)
        db.add(m)
        await db.commit()
        await db.refresh(m)
    return m


async def set_member_role(db: AsyncSession, user_id: str, role: UserRole) -> Membership:
    """Set a user's role in the default org AND sync the users.role mirror."""
    org = await get_default_org(db)
    m = await ensure_membership(db, user_id, org.id, role)
    m.role = role
    user = await db.get(User, user_id)
    if user is not None:
        user.role = role  # mirror (dropped at the contract step)
    await db.commit()
    await db.refresh(m)
    return m


async def count_admins(db: AsyncSession, org_id: str) -> int:
    return await db.scalar(
        select(func.count())
        .select_from(Membership)
        .where(Membership.org_id == org_id, Membership.role == UserRole.ADMIN)
    )
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `python -m pytest tests/test_orgs_service.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/ backend/tests/test_orgs_service.py
git commit -m "feat(orgs): role service with users.role mirror sync"
```

---

## Task 4: Auth deps — get_current_membership + require_org_role (additive)

**Files:**
- Modify: `backend/app/auth/deps.py`
- Test: `backend/tests/test_org_members.py` (created here, expanded in Task 5)

- [ ] **Step 1: Add to `backend/app/auth/deps.py`** (append; do not touch existing functions)

```python
from app.models.org import Membership
from app.services.orgs import get_default_org


async def get_current_membership(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Membership:
    org = await get_default_org(db)
    m = await db.scalar(
        select(Membership).where(
            Membership.user_id == user.id, Membership.org_id == org.id
        )
    )
    if m is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No membership")
    return m


def require_org_role(*roles: UserRole):
    async def _guard(m: Membership = Depends(get_current_membership)) -> Membership:
        if m.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient role"
            )
        return m

    return _guard
```
Add the needed imports at the top: `from sqlalchemy import select` (if missing).

- [ ] **Step 2: Smoke-check import**

Run: `python -c "from app.auth.deps import get_current_membership, require_org_role; print('ok')"`
Expected: `ok`.

- [ ] **Step 3: Commit**

```bash
git add backend/app/auth/deps.py
git commit -m "feat(orgs): additive get_current_membership + require_org_role guard"
```

---

## Task 5: Members API — list + promote (last-admin guard)

**Files:**
- Create: `backend/app/schemas/org.py`
- Create: `backend/app/api/org.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_org_members.py`

- [ ] **Step 1: Write the schemas** (`backend/app/schemas/org.py`)

```python
from datetime import datetime

from pydantic import EmailStr, Field

from app.models.user import UserRole
from app.schemas.auth import CamelModel


class MemberOut(CamelModel):
    user_id: str
    email: EmailStr
    display_name: str
    role: UserRole
    joined_at: datetime


class RoleUpdate(CamelModel):
    role: UserRole


class InviteCreate(CamelModel):
    email: EmailStr
    role: UserRole = UserRole.INSTRUCTOR


class InvitationOut(CamelModel):
    id: str
    email: EmailStr
    role: UserRole
    status: str
    invite_url: str | None = None
    expires_at: datetime


class InvitePreview(CamelModel):
    org_name: str
    email: EmailStr
    role: UserRole
```

- [ ] **Step 2: Write the failing test** (`backend/tests/test_org_members.py`)

```python
from app.auth.security import hash_password
from app.models.user import User, UserRole
from app.services.orgs import ensure_default_org, ensure_membership

_PW = "passphrase-1234"


async def _user_with_role(session, email, role):
    u = User(email=email, hashed_password=hash_password(_PW),
             display_name=email.split("@")[0], role=UserRole(role))
    session.add(u); await session.commit()
    org = await ensure_default_org(session)
    await ensure_membership(session, u.id, org.id, UserRole(role))
    return u


async def _login(client, email):
    client.cookies.clear()
    await client.post("/api/auth/login", json={"email": email, "password": _PW})


async def test_admin_lists_members_and_promotes(client, session):
    admin = await _user_with_role(session, "admin@x.com", "ADMIN")
    stu = await _user_with_role(session, "stu@x.com", "STUDENT")
    await _login(client, "admin@x.com")

    r = await client.get("/api/org/members")
    assert r.status_code == 200
    assert {m["email"] for m in r.json()} == {"admin@x.com", "stu@x.com"}

    r = await client.patch(f"/api/org/members/{stu.id}/role", json={"role": "INSTRUCTOR"})
    assert r.status_code == 200 and r.json()["role"] == "INSTRUCTOR"
    await session.refresh(stu)
    assert stu.role is UserRole.INSTRUCTOR  # mirror synced


async def test_non_admin_forbidden(client, session):
    await _user_with_role(session, "admin@x.com", "ADMIN")
    await _user_with_role(session, "stu@x.com", "STUDENT")
    await _login(client, "stu@x.com")
    assert (await client.get("/api/org/members")).status_code == 403


async def test_cannot_demote_last_admin(client, session):
    admin = await _user_with_role(session, "admin@x.com", "ADMIN")
    await _login(client, "admin@x.com")
    r = await client.patch(f"/api/org/members/{admin.id}/role", json={"role": "STUDENT"})
    assert r.status_code == 409
```

- [ ] **Step 3: Run to verify it fails**

Run: `python -m pytest tests/test_org_members.py -q`
Expected: FAIL — `/api/org/members` 404 (router not mounted).

- [ ] **Step 4: Write the router** (`backend/app/api/org.py`)

```python
"""Org admin: members + role management (admin-gated)."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import require_org_role
from app.db.session import get_db
from app.models.org import Membership
from app.models.user import User, UserRole
from app.schemas.org import MemberOut, RoleUpdate
from app.services.orgs import count_admins, get_default_org, set_member_role

router = APIRouter(prefix="/org", tags=["org"])

_admin = require_org_role(UserRole.ADMIN)


@router.get("/members", response_model=list[MemberOut])
async def list_members(
    m=Depends(_admin), db: AsyncSession = Depends(get_db)
) -> list[MemberOut]:
    org = await get_default_org(db)
    rows = (
        await db.execute(
            select(Membership, User)
            .join(User, User.id == Membership.user_id)
            .where(Membership.org_id == org.id)
            .order_by(User.display_name)
        )
    ).all()
    return [
        MemberOut(
            user_id=u.id, email=u.email, display_name=u.display_name,
            role=mem.role, joined_at=mem.created_at,
        )
        for mem, u in rows
    ]


@router.patch("/members/{user_id}/role", response_model=MemberOut)
async def set_role(
    user_id: str,
    body: RoleUpdate,
    m=Depends(_admin),
    db: AsyncSession = Depends(get_db),
) -> MemberOut:
    org = await get_default_org(db)
    target = await db.scalar(
        select(Membership).where(
            Membership.user_id == user_id, Membership.org_id == org.id
        )
    )
    if target is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Member not found")
    # Block removing the last admin.
    if target.role is UserRole.ADMIN and body.role is not UserRole.ADMIN:
        if await count_admins(db, org.id) <= 1:
            raise HTTPException(status.HTTP_409_CONFLICT, "Org must keep one admin")
    await set_member_role(db, user_id, body.role)
    user = await db.get(User, user_id)
    updated = await db.scalar(
        select(Membership).where(
            Membership.user_id == user_id, Membership.org_id == org.id
        )
    )
    return MemberOut(
        user_id=user.id, email=user.email, display_name=user.display_name,
        role=updated.role, joined_at=updated.created_at,
    )
```

- [ ] **Step 5: Mount the router** in `backend/app/main.py` — add `org` to the feature-router import and include it:

```python
from app.api import assignments, auth, courses, live, org, sessions, webhooks  # + org
...
app.include_router(org.router, prefix="/api")
```
(Leave the `leaderboard`/`notes` imports as they are if present.)

- [ ] **Step 6: Run to verify it passes**

Run: `python -m pytest tests/test_org_members.py -q`
Expected: PASS (3 tests).

- [ ] **Step 7: Commit**

```bash
git add backend/app/schemas/org.py backend/app/api/org.py backend/app/main.py backend/tests/test_org_members.py
git commit -m "feat(orgs): admin members API — list + promote (last-admin guard)"
```

---

## Task 6: Invitations API — create link, list, revoke, public preview

**Files:**
- Modify: `backend/app/api/org.py`
- Test: `backend/tests/test_org_invitations.py`

- [ ] **Step 1: Write the failing test** (`backend/tests/test_org_invitations.py`)

```python
from app.auth.security import hash_password
from app.models.user import User, UserRole
from app.services.orgs import ensure_default_org, ensure_membership

_PW = "passphrase-1234"


async def _admin(session, client):
    u = User(email="admin@x.com", hashed_password=hash_password(_PW),
             display_name="admin", role=UserRole.ADMIN)
    session.add(u); await session.commit()
    org = await ensure_default_org(session)
    await ensure_membership(session, u.id, org.id, UserRole.ADMIN)
    client.cookies.clear()
    await client.post("/api/auth/login", json={"email": "admin@x.com", "password": _PW})
    return u


async def test_invite_create_list_revoke_and_public_preview(client, session):
    await _admin(session, client)

    r = await client.post("/api/org/invitations",
                          json={"email": "prof@uni.edu", "role": "INSTRUCTOR"})
    assert r.status_code == 201
    body = r.json()
    assert body["inviteUrl"].endswith(body["id"]) is False  # url carries a token, not id
    token = body["inviteUrl"].split("invite=")[-1]

    # public preview (no auth)
    client.cookies.clear()
    p = await client.get(f"/api/invitations/{token}")
    assert p.status_code == 200
    assert p.json() == {"orgName": "nodeLive", "email": "prof@uni.edu", "role": "INSTRUCTOR"}

    # list + revoke (admin)
    await client.post("/api/auth/login", json={"email": "admin@x.com", "password": _PW})
    assert len((await client.get("/api/org/invitations")).json()) == 1
    inv_id = (await client.get("/api/org/invitations")).json()[0]["id"]
    assert (await client.delete(f"/api/org/invitations/{inv_id}")).status_code == 204
    assert len((await client.get("/api/org/invitations")).json()) == 0
```

- [ ] **Step 2: Run to verify it fails**

Run: `python -m pytest tests/test_org_invitations.py -q`
Expected: FAIL — invitations endpoints 404.

- [ ] **Step 3: Add invitation endpoints** to `backend/app/api/org.py`

```python
import secrets
from datetime import UTC, datetime, timedelta

from app.core.config import settings
from app.models.org import Invitation, InvitationStatus
from app.schemas.org import InviteCreate, InvitationOut, InvitePreview


def _invite_url(token: str) -> str:
    base = settings.cors_origins[0] if settings.cors_origins else ""
    return f"{base}/signup?invite={token}"


@router.post("/invitations", response_model=InvitationOut, status_code=status.HTTP_201_CREATED)
async def create_invitation(
    body: InviteCreate,
    m: Membership = Depends(_admin),
    db: AsyncSession = Depends(get_db),
) -> InvitationOut:
    org = await get_default_org(db)
    already = await db.scalar(
        select(Membership).join(User, User.id == Membership.user_id).where(
            Membership.org_id == org.id, User.email == body.email
        )
    )
    if already is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Already a member")
    inv = Invitation(
        org_id=org.id, email=body.email, role=body.role,
        token=secrets.token_urlsafe(32), invited_by=m.user_id,
        expires_at=datetime.now(UTC) + timedelta(days=7),
    )
    db.add(inv)
    await db.commit()
    await db.refresh(inv)
    return InvitationOut(
        id=inv.id, email=inv.email, role=inv.role, status=inv.status.value,
        invite_url=_invite_url(inv.token), expires_at=inv.expires_at,
    )


@router.get("/invitations", response_model=list[InvitationOut])
async def list_invitations(
    m=Depends(_admin), db: AsyncSession = Depends(get_db)
) -> list[InvitationOut]:
    org = await get_default_org(db)
    rows = list(
        await db.scalars(
            select(Invitation).where(
                Invitation.org_id == org.id,
                Invitation.status == InvitationStatus.PENDING,
            ).order_by(Invitation.created_at.desc())
        )
    )
    return [
        InvitationOut(id=i.id, email=i.email, role=i.role, status=i.status.value,
                      invite_url=_invite_url(i.token), expires_at=i.expires_at)
        for i in rows
    ]


@router.delete("/invitations/{invite_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_invitation(
    invite_id: str, m=Depends(_admin), db: AsyncSession = Depends(get_db)
) -> None:
    inv = await db.get(Invitation, invite_id)
    if inv is not None:
        inv.status = InvitationStatus.REVOKED
        await db.commit()
```

Add a **public** preview route in a second router so it isn't admin-gated. In
`backend/app/api/org.py`, add:

```python
public_router = APIRouter(tags=["org"])


@public_router.get("/invitations/{token}", response_model=InvitePreview)
async def preview_invitation(token: str, db: AsyncSession = Depends(get_db)) -> InvitePreview:
    inv = await db.scalar(select(Invitation).where(Invitation.token == token))
    org = await get_default_org(db)
    if (
        inv is None
        or inv.status is not InvitationStatus.PENDING
        or inv.expires_at < datetime.now(UTC)
    ):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Invite not found")
    return InvitePreview(org_name=org.name, email=inv.email, role=inv.role)
```

- [ ] **Step 4: Mount the public router** in `backend/app/main.py`:

```python
app.include_router(org.public_router, prefix="/api")
```

- [ ] **Step 5: Run to verify it passes**

Run: `python -m pytest tests/test_org_invitations.py -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/api/org.py backend/app/main.py backend/tests/test_org_invitations.py
git commit -m "feat(orgs): invitations API + public preview"
```

---

## Task 7: Signup accepts an invite token

**Files:**
- Modify: `backend/app/schemas/auth.py`
- Modify: `backend/app/api/auth.py`
- Test: `backend/tests/test_signup_invite.py`

- [ ] **Step 1: Add `invite_token` to `SignupIn`** in `backend/app/schemas/auth.py`:

```python
class SignupIn(CamelModel):
    email: EmailStr
    password: str
    display_name: str
    invite_token: str | None = None
```

- [ ] **Step 2: Write the failing test** (`backend/tests/test_signup_invite.py`)

```python
import secrets
from datetime import UTC, datetime, timedelta

from app.auth.security import hash_password
from app.models.org import Invitation
from app.models.user import User, UserRole
from app.services.orgs import ensure_default_org, ensure_membership


async def _seed_admin_and_invite(session, email, role="INSTRUCTOR"):
    admin = User(email="admin@x.com", hashed_password=hash_password("pw-123456"),
                 display_name="admin", role=UserRole.ADMIN)
    session.add(admin); await session.commit()
    org = await ensure_default_org(session)
    await ensure_membership(session, admin.id, org.id, UserRole.ADMIN)
    inv = Invitation(org_id=org.id, email=email, role=UserRole(role),
                     token=secrets.token_urlsafe(16), invited_by=admin.id,
                     expires_at=datetime.now(UTC) + timedelta(days=7))
    session.add(inv); await session.commit()
    return inv


async def test_signup_with_matching_invite_gets_role(client, session):
    inv = await _seed_admin_and_invite(session, "prof@uni.edu", "INSTRUCTOR")
    r = await client.post("/api/auth/signup", json={
        "email": "prof@uni.edu", "password": "pw-123456",
        "displayName": "Prof", "inviteToken": inv.token,
    })
    assert r.status_code == 201
    assert r.json()["role"] == "INSTRUCTOR"


async def test_signup_with_mismatched_email_rejected(client, session):
    inv = await _seed_admin_and_invite(session, "prof@uni.edu", "INSTRUCTOR")
    r = await client.post("/api/auth/signup", json={
        "email": "someone-else@x.com", "password": "pw-123456",
        "displayName": "X", "inviteToken": inv.token,
    })
    assert r.status_code == 400


async def test_signup_without_invite_is_student(client, session):
    await ensure_default_org(session)
    r = await client.post("/api/auth/signup", json={
        "email": "s@x.com", "password": "pw-123456", "displayName": "S",
    })
    assert r.status_code == 201 and r.json()["role"] == "STUDENT"
```

- [ ] **Step 3: Run to verify it fails**

Run: `python -m pytest tests/test_signup_invite.py -q`
Expected: FAIL — role is `STUDENT` for the invited user (invite not honored) / mismatch not rejected.

- [ ] **Step 4: Update `signup`** in `backend/app/api/auth.py` — after creating the user, resolve the invite and set the membership+mirror:

```python
from datetime import UTC, datetime

from sqlalchemy import select

from app.models.org import Invitation, InvitationStatus
from app.models.user import UserRole
from app.services.orgs import ensure_default_org, set_member_role


@router.post("/signup", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def signup(body: SignupIn, response: Response, db: AsyncSession = Depends(get_db)) -> User:
    existing = await db.scalar(select(User).where(User.email == body.email))
    if existing is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Email already registered")

    role = UserRole.STUDENT
    invite = None
    if body.invite_token:
        invite = await db.scalar(
            select(Invitation).where(Invitation.token == body.invite_token)
        )
        if (
            invite is None
            or invite.status is not InvitationStatus.PENDING
            or invite.expires_at < datetime.now(UTC)
            or invite.email.lower() != body.email.lower()
        ):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid or mismatched invite")
        role = invite.role

    user = User(
        email=body.email, hashed_password=hash_password(body.password),
        display_name=body.display_name, role=role,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    org = await ensure_default_org(db)
    await set_member_role(db, user.id, role)  # creates membership + keeps mirror
    if invite is not None:
        invite.status = InvitationStatus.ACCEPTED
        invite.accepted_at = datetime.now(UTC)
        await db.commit()

    _set_session_cookie(response, create_access_token(user.id))
    return user
```

> `set_member_role` calls `ensure_membership` then syncs — for a brand-new user it
> creates the membership with `role`. `User.role` was already set to `role` above,
> so the mirror is consistent.

- [ ] **Step 5: Run to verify it passes**

Run: `python -m pytest tests/test_signup_invite.py -q`
Expected: PASS (3 tests).

- [ ] **Step 6: Commit**

```bash
git add backend/app/schemas/auth.py backend/app/api/auth.py backend/tests/test_signup_invite.py
git commit -m "feat(orgs): signup accepts email-locked invite token → assigns role"
```

---

## Task 8: Update seed + set_role to write membership + make instructor an ADMIN

**Files:**
- Modify: `backend/scripts/set_role.py`
- Modify: `backend/scripts/seed.py`

- [ ] **Step 1: Update `set_role`** to go through the service (membership + mirror). Replace the body of `set_role(...)`:

```python
from app.services.orgs import ensure_default_org, set_member_role

async def set_role(email: str, role: str) -> None:
    try:
        new_role = UserRole(role.upper())
    except ValueError:
        valid = ", ".join(r.value for r in UserRole)
        print(f"Invalid role {role!r}. Use one of: {valid}")
        raise SystemExit(1) from None
    async with AsyncSessionLocal() as db:
        user = await db.scalar(select(User).where(User.email == email))
        if user is None:
            print(f"No user with email {email!r}.")
            raise SystemExit(1)
        await ensure_default_org(db)
        await set_member_role(db, user.id, new_role)
        print(f"✓ {email} is now {new_role.value} (membership + mirror)")
```

- [ ] **Step 2: Update `seed`** — after creating users, ensure the default org and memberships, and make the instructor an org **ADMIN**. In `backend/scripts/seed.py`, after the bulk insert commit add:

```python
from app.services.orgs import ensure_default_org, ensure_membership, set_member_role
...
        await db.commit()
        await _ensure_live_session(db)
        org = await ensure_default_org(db)
        for u in (instructor, *students):
            await ensure_membership(db, u.id, org.id, u.role)
        await set_member_role(db, instructor.id, UserRole.ADMIN)  # seeded admin
```
And in the "already present" branch, also `await ensure_default_org(db)` and
`await set_member_role(db, <instructor id>, UserRole.ADMIN)` so re-runs bootstrap
an admin. (Look up the instructor by email `instructor@nodelive.dev`.)

- [ ] **Step 3: Verify against the local dev DB**

```bash
python -m scripts.seed
python -m scripts.set_role student1@nodelive.dev INSTRUCTOR
python -m scripts.set_role student1@nodelive.dev STUDENT
```
Expected: seed prints the LIVE-session + no error; `set_role` prints the ✓ lines.

- [ ] **Step 4: Commit**

```bash
git add backend/scripts/set_role.py backend/scripts/seed.py
git commit -m "feat(orgs): seed/set_role write memberships; seed bootstraps an org ADMIN"
```

---

## Task 9: Full suite + lint gate

- [ ] **Step 1: Run the whole backend suite**

Run: `python -m pytest -q`
Expected: all prior tests **still pass** (AF is additive) + the new org tests pass.

- [ ] **Step 2: Lint + format**

Run: `ruff check app tests scripts && ruff format --check app tests scripts`
Expected: clean (fix anything flagged, e.g. unused imports, then re-run).

- [ ] **Step 3: Migration round-trip once more** (Task 2 Step 3 commands) to confirm head is clean.

- [ ] **Step 4: Commit any lint fixes**

```bash
git add -A backend
git commit -m "chore(orgs): lint + format"
```

---

## Self-review notes (already applied)
- **Spec coverage:** models, migration+backfill (keep `users.role`), role service with mirror sync, additive `require_org_role`, members list + promote + last-admin guard, invitations + public preview, email-locked signup, seed/set_role + admin bootstrap — all mapped to tasks.
- **Non-breaking check:** no existing guard/serializer/test is modified (only additions) → Task 9 Step 1 proves it.
- **Type consistency:** `set_member_role`, `ensure_membership`, `get_default_org`, `require_org_role`, `MemberOut`, `InvitationOut`, `InvitePreview` names match across tasks.

## Out of scope (separate plans)
- **Members admin UI** + signup invite handling (frontend).
- AD tabs: **Sessions**, **Attendance**, **Overview**.
- **Contract step:** migrate readers to membership, drop `users.role`.
