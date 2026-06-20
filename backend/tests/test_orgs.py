"""AF — organizations, memberships, role-sync service, invite-accept signup."""

from datetime import UTC, datetime, timedelta

import pytest
from fastapi import HTTPException
from sqlalchemy import func, select

from app.auth.deps import require_org_role
from app.auth.security import hash_password
from app.models.org import (
    DEFAULT_ORG_SLUG,
    Invitation,
    InvitationStatus,
    Membership,
    Organization,
)
from app.models.user import User, UserRole
from app.services.roles import (
    assign_role,
    count_org_admins,
    get_or_create_default_org,
    get_or_create_membership,
)

_PW = "passphrase-1234"


async def _user(session, email, role=UserRole.STUDENT):
    u = User(
        email=email,
        hashed_password=hash_password(_PW),
        display_name=email.split("@")[0],
        role=role,
    )
    session.add(u)
    await session.commit()
    return u


# --- service: default org + membership + role sync ---------------------------


async def test_default_org_is_idempotent(session):
    a = await get_or_create_default_org(session)
    b = await get_or_create_default_org(session)
    assert a.id == b.id
    assert a.slug == DEFAULT_ORG_SLUG
    count = await session.scalar(select(func.count()).select_from(Organization))
    assert count == 1


async def test_membership_lazy_backfill_from_mirror(session):
    u = await _user(session, "s@x.com", UserRole.INSTRUCTOR)
    m = await get_or_create_membership(session, u)
    # backfilled from the User.role mirror
    assert m.role == UserRole.INSTRUCTOR
    # idempotent — no duplicate membership
    m2 = await get_or_create_membership(session, u)
    assert m2.id == m.id


async def test_assign_role_syncs_membership_and_mirror(session):
    u = await _user(session, "p@x.com", UserRole.STUDENT)
    m = await assign_role(session, u, UserRole.ADMIN)
    await session.commit()
    assert m.role == UserRole.ADMIN
    assert u.role == UserRole.ADMIN  # mirror kept in sync
    fetched = await session.get(Membership, m.id)
    assert fetched.role == UserRole.ADMIN


async def test_count_org_admins(session):
    org = await get_or_create_default_org(session)
    a = await _user(session, "a@x.com")
    b = await _user(session, "b@x.com")
    await assign_role(session, a, UserRole.ADMIN)
    await assign_role(session, b, UserRole.STUDENT)
    await session.commit()
    assert await count_org_admins(session, org) == 1


# --- require_org_role guard --------------------------------------------------


async def test_require_org_role_allows_and_blocks(session):
    org = await get_or_create_default_org(session)
    admin = await _user(session, "adm@x.com")
    student = await _user(session, "stu@x.com")
    am = await assign_role(session, admin, UserRole.ADMIN, org)
    sm = await assign_role(session, student, UserRole.STUDENT, org)
    await session.commit()

    guard = require_org_role(UserRole.ADMIN)
    assert await guard(membership=am) is am
    with pytest.raises(HTTPException) as exc:
        await guard(membership=sm)
    assert exc.value.status_code == 403


# --- signup invite-accept (email-locked) -------------------------------------


async def _invite(session, email, role=UserRole.INSTRUCTOR, **over):
    org = await get_or_create_default_org(session)
    inv = Invitation(
        org_id=org.id,
        email=email,
        role=role,
        token=over.get("token", "tok-" + email),
        status=over.get("status", InvitationStatus.PENDING),
        expires_at=over.get("expires_at", datetime.now(UTC) + timedelta(days=7)),
    )
    session.add(inv)
    await session.commit()
    return inv


async def test_signup_with_valid_invite_assigns_role(client, session):
    await _invite(session, "newprof@x.com", UserRole.INSTRUCTOR)
    r = await client.post(
        "/api/auth/signup",
        json={
            "email": "newprof@x.com",
            "password": _PW,
            "displayName": "New Prof",
            "inviteToken": "tok-newprof@x.com",
        },
    )
    assert r.status_code == 201
    assert r.json()["role"] == "INSTRUCTOR"

    u = await session.scalar(select(User).where(User.email == "newprof@x.com"))
    m = await session.scalar(select(Membership).where(Membership.user_id == u.id))
    assert m.role == UserRole.INSTRUCTOR
    inv = await session.scalar(
        select(Invitation).where(Invitation.email == "newprof@x.com")
    )
    assert inv.status == InvitationStatus.ACCEPTED
    assert inv.accepted_at is not None


async def test_signup_without_invite_is_student(client, session):
    r = await client.post(
        "/api/auth/signup",
        json={"email": "plain@x.com", "password": _PW, "displayName": "Plain"},
    )
    assert r.status_code == 201
    assert r.json()["role"] == "STUDENT"


async def test_signup_invite_email_mismatch_rejected(client, session):
    await _invite(session, "invited@x.com", UserRole.ADMIN)
    r = await client.post(
        "/api/auth/signup",
        json={
            "email": "someoneelse@x.com",
            "password": _PW,
            "displayName": "Imposter",
            "inviteToken": "tok-invited@x.com",
        },
    )
    assert r.status_code == 400


async def test_signup_expired_invite_rejected(client, session):
    await _invite(
        session,
        "late@x.com",
        token="tok-late",
        expires_at=datetime.now(UTC) - timedelta(days=1),
    )
    r = await client.post(
        "/api/auth/signup",
        json={
            "email": "late@x.com",
            "password": _PW,
            "displayName": "Late",
            "inviteToken": "tok-late",
        },
    )
    assert r.status_code == 400


async def test_signup_revoked_invite_rejected(client, session):
    await _invite(
        session, "revoked@x.com", token="tok-rev", status=InvitationStatus.REVOKED
    )
    r = await client.post(
        "/api/auth/signup",
        json={
            "email": "revoked@x.com",
            "password": _PW,
            "displayName": "Rev",
            "inviteToken": "tok-rev",
        },
    )
    assert r.status_code == 400
