"""Admin dashboard — Members & Roles surface (org-ADMIN gated).

Built on the AF foundation: every write goes through `assign_role` so the
membership and the `User.role` mirror stay in sync. The last-admin guard keeps
an org from locking itself out. The invite preview is public so the signup
screen can show "Joining {org} as {role}".
"""

import secrets
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import require_org_role
from app.db.session import get_db
from app.models.course import ClassSession, Course, SessionStatus
from app.models.org import Invitation, InvitationStatus, Membership, Organization
from app.models.user import User, UserRole
from app.schemas.course import CourseCreate, CourseOut
from app.schemas.org import (
    InvitationOut,
    InviteCreate,
    InvitePreview,
    MemberOut,
    RoleUpdate,
)
from app.schemas.session import ClassSessionOut
from app.services.roles import assign_role, count_org_admins

router = APIRouter(prefix="/admin", tags=["admin"])
public_router = APIRouter(tags=["admin"])

_admin = require_org_role(UserRole.ADMIN)

_INVITE_TTL = timedelta(days=7)


def _invite_url(token: str) -> str:
    """Relative link (same-origin in prod); the UI prefixes the current origin."""
    return f"/signup?invite={token}"


def _invite_out(inv: Invitation) -> InvitationOut:
    return InvitationOut(
        id=inv.id,
        email=inv.email,
        role=inv.role,
        status=inv.status,
        token=inv.token,
        invite_url=_invite_url(inv.token),
        created_at=inv.created_at,
        expires_at=inv.expires_at,
    )


# --- members & roles ----------------------------------------------------------


@router.get("/members", response_model=list[MemberOut])
async def list_members(
    membership: Membership = Depends(_admin),
    db: AsyncSession = Depends(get_db),
) -> list[MemberOut]:
    rows = (
        await db.execute(
            select(Membership, User)
            .join(User, User.id == Membership.user_id)
            .where(Membership.org_id == membership.org_id)
            .order_by(User.display_name)
        )
    ).all()
    return [
        MemberOut(
            user_id=u.id,
            email=u.email,
            display_name=u.display_name,
            role=m.role,
            joined_at=m.created_at,
        )
        for m, u in rows
    ]


@router.patch("/members/{user_id}/role", response_model=MemberOut)
async def set_member_role(
    user_id: str,
    body: RoleUpdate,
    membership: Membership = Depends(_admin),
    db: AsyncSession = Depends(get_db),
) -> MemberOut:
    org = await db.get(Organization, membership.org_id)
    target = await db.scalar(
        select(Membership).where(
            Membership.user_id == user_id, Membership.org_id == org.id
        )
    )
    user = await db.get(User, user_id)
    if target is None or user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Member not found")

    # Never let the org drop to zero admins.
    if (
        target.role is UserRole.ADMIN
        and body.role is not UserRole.ADMIN
        and await count_org_admins(db, org) <= 1
    ):
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Cannot remove the last admin of the org"
        )

    updated = await assign_role(db, user, body.role, org)
    await db.commit()
    return MemberOut(
        user_id=user.id,
        email=user.email,
        display_name=user.display_name,
        role=updated.role,
        joined_at=updated.created_at,
    )


# --- invitations --------------------------------------------------------------


@router.post(
    "/invitations", response_model=InvitationOut, status_code=status.HTTP_201_CREATED
)
async def create_invitation(
    body: InviteCreate,
    membership: Membership = Depends(_admin),
    db: AsyncSession = Depends(get_db),
) -> InvitationOut:
    org_id = membership.org_id
    already = await db.scalar(
        select(Membership)
        .join(User, User.id == Membership.user_id)
        .where(Membership.org_id == org_id, User.email == body.email)
    )
    if already is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Already a member of this org")

    inv = Invitation(
        org_id=org_id,
        email=body.email,
        role=body.role,
        token=secrets.token_urlsafe(32),
        invited_by=membership.user_id,
        expires_at=datetime.now(UTC) + _INVITE_TTL,
    )
    db.add(inv)
    await db.commit()
    await db.refresh(inv)
    return _invite_out(inv)


@router.get("/invitations", response_model=list[InvitationOut])
async def list_invitations(
    membership: Membership = Depends(_admin),
    db: AsyncSession = Depends(get_db),
) -> list[InvitationOut]:
    rows = await db.scalars(
        select(Invitation)
        .where(
            Invitation.org_id == membership.org_id,
            Invitation.status == InvitationStatus.PENDING,
        )
        .order_by(Invitation.created_at.desc())
    )
    return [_invite_out(inv) for inv in rows]


@router.delete("/invitations/{invite_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_invitation(
    invite_id: str,
    membership: Membership = Depends(_admin),
    db: AsyncSession = Depends(get_db),
) -> None:
    inv = await db.scalar(
        select(Invitation).where(
            Invitation.id == invite_id, Invitation.org_id == membership.org_id
        )
    )
    if inv is not None and inv.status is InvitationStatus.PENDING:
        inv.status = InvitationStatus.REVOKED
        await db.commit()


# --- sessions (schedule & manage) --------------------------------------------


@router.get("/sessions", response_model=list[ClassSessionOut])
async def list_all_sessions(
    status_filter: SessionStatus | None = Query(default=None, alias="status"),
    membership: Membership = Depends(_admin),
    db: AsyncSession = Depends(get_db),
) -> list[ClassSession]:
    stmt = select(ClassSession)
    if status_filter is not None:
        stmt = stmt.where(ClassSession.status == status_filter)
    stmt = stmt.order_by(ClassSession.scheduled_at.desc())
    return list(await db.scalars(stmt))


@router.post("/sessions/{session_id}/cancel", response_model=ClassSessionOut)
async def cancel_session(
    session_id: str,
    membership: Membership = Depends(_admin),
    db: AsyncSession = Depends(get_db),
) -> ClassSession:
    cs = await db.get(ClassSession, session_id)
    if cs is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Session not found")
    cs.status = SessionStatus.CANCELLED
    await db.commit()
    await db.refresh(cs)
    return cs


@router.get("/courses", response_model=list[CourseOut])
async def list_all_courses(
    membership: Membership = Depends(_admin),
    db: AsyncSession = Depends(get_db),
) -> list[Course]:
    return list(await db.scalars(select(Course).order_by(Course.title)))


@router.post("/courses", response_model=CourseOut, status_code=status.HTTP_201_CREATED)
async def create_course(
    body: CourseCreate,
    membership: Membership = Depends(_admin),
    db: AsyncSession = Depends(get_db),
) -> Course:
    title = body.title.strip()
    if not title:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Title required")
    course = Course(title=title)
    db.add(course)
    await db.commit()
    await db.refresh(course)
    return course


# --- public preview (signup screen) ------------------------------------------


@public_router.get("/invitations/{token}", response_model=InvitePreview)
async def preview_invitation(
    token: str,
    db: AsyncSession = Depends(get_db),
) -> InvitePreview:
    inv = await db.scalar(select(Invitation).where(Invitation.token == token))
    not_found = HTTPException(status.HTTP_404_NOT_FOUND, "Invitation not found")
    if inv is None or inv.status is not InvitationStatus.PENDING:
        raise not_found
    if inv.expires_at is not None and inv.expires_at < datetime.now(UTC):
        raise not_found
    org = await db.get(Organization, inv.org_id)
    return InvitePreview(org_name=org.name, email=inv.email, role=inv.role)
