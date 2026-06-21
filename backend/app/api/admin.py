"""Admin dashboard — Members & Roles surface (org-ADMIN gated).

Built on the AF foundation: every write goes through `assign_role` so the
membership and the `User.role` mirror stay in sync. The last-admin guard keeps
an org from locking itself out. The invite preview is public so the signup
screen can show "Joining {org} as {role}".
"""

import logging
import secrets
from datetime import UTC, datetime, timedelta

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, nulls_last, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import require_org_role
from app.db.session import get_db
from app.models.attendance import AttendanceFinal, Meeting
from app.models.course import ClassSession, Course, Enrollment, SessionStatus
from app.models.org import Invitation, InvitationStatus, Membership, Organization
from app.models.user import User, UserRole
from app.schemas.course import CourseCreate, CourseOut
from app.schemas.org import (
    AttendeeOut,
    EnrollmentCreate,
    EnrollmentOut,
    InvitationOut,
    InviteCreate,
    InvitePreview,
    MemberOut,
    OverviewOut,
    RoleUpdate,
    SessionStatusCounts,
    SyncAttendanceOut,
    UpcomingSessionOut,
)
from app.schemas.session import ClassSessionOut
from app.services.enrollment import enroll_all_users
from app.services.roles import assign_role, count_org_admins
from app.utils import zoom_meetings
from app.workers import attendance_tasks

logger = logging.getLogger(__name__)

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


@router.post("/sessions/{session_id}/end", response_model=ClassSessionOut)
async def end_session(
    session_id: str,
    membership: Membership = Depends(_admin),
    db: AsyncSession = Depends(get_db),
) -> ClassSession:
    """Manually end a session — admin fallback for when the Zoom webhook never
    fires. Marks it ENDED and triggers the attendance reconcile if a Meeting
    record exists, so the Attendance tab can surface the just-ended session."""
    cs = await db.get(ClassSession, session_id)
    if cs is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Session not found")
    if cs.status not in (SessionStatus.SCHEDULED, SessionStatus.LIVE):
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Session is already ended or cancelled"
        )

    cs.status = SessionStatus.ENDED
    cs.ended_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(cs)

    if cs.zoom_meeting_id:
        meeting = await db.scalar(
            select(Meeting)
            .where(Meeting.zoom_meeting_id == cs.zoom_meeting_id)
            .order_by(nulls_last(Meeting.ended_at.desc()))
            .limit(1)
        )
        if meeting is not None:
            attendance_tasks.schedule_reconcile(meeting.zoom_uuid)
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
    await db.flush()
    # Single-org: enroll every member so sessions in this course are visible.
    await enroll_all_users(db, course.id)
    await db.commit()
    await db.refresh(course)
    return course


# --- instructor list (for host picker) ----------------------------------------


@router.get("/instructors", response_model=list[MemberOut])
async def list_instructors(
    membership: Membership = Depends(_admin),
    db: AsyncSession = Depends(get_db),
) -> list[MemberOut]:
    """Members with INSTRUCTOR or ADMIN role — used to populate the host picker."""
    rows = (
        await db.execute(
            select(Membership, User)
            .join(User, User.id == Membership.user_id)
            .where(
                Membership.org_id == membership.org_id,
                Membership.role.in_([UserRole.INSTRUCTOR, UserRole.ADMIN]),
            )
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


# --- enrollment management ----------------------------------------------------


@router.get("/enrollments", response_model=list[EnrollmentOut])
async def list_enrollments(
    course_id: str | None = Query(default=None, alias="courseId"),
    membership: Membership = Depends(_admin),
    db: AsyncSession = Depends(get_db),
) -> list[EnrollmentOut]:
    stmt = (
        select(Enrollment, User, Course)
        .join(User, User.id == Enrollment.user_id)
        .join(Course, Course.id == Enrollment.course_id)
        .order_by(User.display_name)
    )
    if course_id is not None:
        stmt = stmt.where(Enrollment.course_id == course_id)
    rows = (await db.execute(stmt)).all()
    return [
        EnrollmentOut(
            id=e.id,
            user_id=e.user_id,
            course_id=e.course_id,
            display_name=u.display_name,
            email=u.email,
            course_title=c.title,
        )
        for e, u, c in rows
    ]


@router.post(
    "/enrollments",
    response_model=EnrollmentOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_enrollment(
    body: EnrollmentCreate,
    membership: Membership = Depends(_admin),
    db: AsyncSession = Depends(get_db),
) -> EnrollmentOut:
    existing = await db.scalar(
        select(Enrollment).where(
            Enrollment.user_id == body.user_id,
            Enrollment.course_id == body.course_id,
        )
    )
    if existing is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Already enrolled")
    user = await db.get(User, body.user_id)
    course = await db.get(Course, body.course_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    if course is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Course not found")
    enr = Enrollment(user_id=body.user_id, course_id=body.course_id)
    db.add(enr)
    await db.commit()
    await db.refresh(enr)
    return EnrollmentOut(
        id=enr.id,
        user_id=enr.user_id,
        course_id=enr.course_id,
        display_name=user.display_name,
        email=user.email,
        course_title=course.title,
    )


@router.delete("/enrollments/{enrollment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_enrollment(
    enrollment_id: str,
    membership: Membership = Depends(_admin),
    db: AsyncSession = Depends(get_db),
) -> None:
    enr = await db.get(Enrollment, enrollment_id)
    if enr is not None:
        await db.delete(enr)
        await db.commit()


# --- attendance ---------------------------------------------------------------


@router.get("/sessions/{session_id}/attendance", response_model=list[AttendeeOut])
async def session_attendance(
    session_id: str,
    membership: Membership = Depends(_admin),
    db: AsyncSession = Depends(get_db),
) -> list[AttendeeOut]:
    cs = await db.get(ClassSession, session_id)
    if cs is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Session not found")

    # Fetch enrolled users for this session's course.
    rows = (
        (
            await db.execute(
                select(User)
                .join(Enrollment, Enrollment.user_id == User.id)
                .where(Enrollment.course_id == cs.course_id)
                .order_by(User.display_name)
            )
        )
        .scalars()
        .all()
    )

    # Find all Zoom meeting occurrences for this session's zoom_meeting_id.
    # AttendanceFinal.user_id is the app user id (set via customerKey in join).
    present: dict[str, int] = {}
    if cs.zoom_meeting_id:
        zoom_uuids = (
            (
                await db.execute(
                    select(Meeting.zoom_uuid).where(
                        Meeting.zoom_meeting_id == cs.zoom_meeting_id
                    )
                )
            )
            .scalars()
            .all()
        )
        if zoom_uuids:
            finals = (
                (
                    await db.execute(
                        select(AttendanceFinal).where(
                            AttendanceFinal.zoom_uuid.in_(zoom_uuids),
                            AttendanceFinal.user_id.is_not(None),
                        )
                    )
                )
                .scalars()
                .all()
            )
            for af in finals:
                uid = af.user_id
                present[uid] = present.get(uid, 0) + af.present_seconds

    return [
        AttendeeOut(
            user_id=u.id,
            display_name=u.display_name,
            email=u.email,
            present_seconds=present.get(u.id, 0),
            attended=u.id in present,
        )
        for u in rows
    ]


@router.post("/sessions/{session_id}/sync-attendance", response_model=SyncAttendanceOut)
async def sync_attendance(
    session_id: str,
    membership: Membership = Depends(_admin),
    db: AsyncSession = Depends(get_db),
) -> SyncAttendanceOut:
    """Pull attendance straight from the Zoom Reports API on demand.

    Works WITHOUT the webhook spine: it resolves the meeting instance UUIDs via
    `/past_meetings/{number}/instances`, upserts the Meeting rows the Attendance
    tab joins on, and runs the reconcile synchronously. Returns a diagnostic so
    the exact failure (Reports-API plan/scope, no report yet) is visible."""
    cs = await db.get(ClassSession, session_id)
    if cs is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Session not found")
    if not cs.zoom_meeting_id:
        return SyncAttendanceOut(ok=False, error="This session has no Zoom meeting ID.")
    if not zoom_meetings.s2s_configured():
        return SyncAttendanceOut(
            ok=False, error="Zoom Server-to-Server OAuth is not configured."
        )

    try:
        # Known instances (from webhooks, if any) + every past occurrence Zoom
        # knows about. dict.fromkeys preserves order and de-dupes.
        known = list(
            await db.scalars(
                select(Meeting.zoom_uuid).where(
                    Meeting.zoom_meeting_id == cs.zoom_meeting_id
                )
            )
        )
        # Listing past instances is best-effort: if its scope is missing but a
        # webhook already recorded a Meeting row, reconcile that instead of
        # failing outright.
        instances_err: str | None = None
        try:
            instances = await zoom_meetings.get_past_instances(cs.zoom_meeting_id)
        except httpx.HTTPStatusError as e:
            instances = []
            instances_err = (
                f"Zoom API {e.response.status_code}: {(e.response.text or '')[:200]}"
            )
        uuids = list(dict.fromkeys([*known, *instances]))
        if not uuids:
            return SyncAttendanceOut(
                ok=False,
                error=instances_err
                or "No past meeting instances found yet — Zoom may still be "
                "finalizing the report (try again in a few minutes).",
            )

        # Ensure a Meeting row exists per instance so the Attendance tab resolves.
        for u in uuids:
            existing = await db.scalar(select(Meeting).where(Meeting.zoom_uuid == u))
            if existing is None:
                db.add(Meeting(zoom_uuid=u, zoom_meeting_id=cs.zoom_meeting_id))
        await db.commit()

        total = 0
        for u in uuids:
            total += await attendance_tasks.run_reconcile(u)
        return SyncAttendanceOut(ok=True, instances=len(uuids), attendees=total)
    except httpx.HTTPStatusError as e:
        detail = (e.response.text or "")[:200]
        logger.exception("sync-attendance Zoom API error for session %s", session_id)
        return SyncAttendanceOut(
            ok=False, error=f"Zoom API {e.response.status_code}: {detail}"
        )
    except Exception as e:  # noqa: BLE001 - surface any failure to the admin
        logger.exception("sync-attendance failed for session %s", session_id)
        return SyncAttendanceOut(ok=False, error=str(e) or "Unknown error")


# --- overview -----------------------------------------------------------------


@router.get("/overview", response_model=OverviewOut)
async def overview(
    membership: Membership = Depends(_admin),
    db: AsyncSession = Depends(get_db),
) -> OverviewOut:
    # Member counts by role
    role_rows = (
        await db.execute(
            select(Membership.role, func.count().label("n"))
            .where(Membership.org_id == membership.org_id)
            .group_by(Membership.role)
        )
    ).all()
    role_map: dict[str, int] = {r.role.value: r.n for r in role_rows}

    # Session counts by status
    status_rows = (
        await db.execute(
            select(ClassSession.status, func.count().label("n")).group_by(
                ClassSession.status
            )
        )
    ).all()
    status_map: dict[str, int] = {r.status.value: r.n for r in status_rows}

    total_courses = await db.scalar(select(func.count()).select_from(Course))
    total_enrollments = await db.scalar(select(func.count()).select_from(Enrollment))

    now = datetime.now(UTC)
    upcoming_rows = (
        await db.scalars(
            select(ClassSession)
            .where(
                ClassSession.status == SessionStatus.SCHEDULED,
                ClassSession.scheduled_at >= now,
            )
            .order_by(ClassSession.scheduled_at)
            .limit(5)
        )
    ).all()

    total_members = sum(role_map.values())
    return OverviewOut(
        total_members=total_members,
        students=role_map.get(UserRole.STUDENT.value, 0),
        instructors=role_map.get(UserRole.INSTRUCTOR.value, 0),
        admins=role_map.get(UserRole.ADMIN.value, 0),
        total_courses=total_courses or 0,
        total_enrollments=total_enrollments or 0,
        sessions=SessionStatusCounts(
            scheduled=status_map.get(SessionStatus.SCHEDULED.value, 0),
            live=status_map.get(SessionStatus.LIVE.value, 0),
            ended=status_map.get(SessionStatus.ENDED.value, 0),
            cancelled=status_map.get(SessionStatus.CANCELLED.value, 0),
        ),
        upcoming=[
            UpcomingSessionOut(
                id=cs.id,
                title=cs.title,
                scheduled_at=cs.scheduled_at,
                duration_mins=cs.duration_mins,
                status=cs.status.value,
            )
            for cs in upcoming_rows
        ],
    )


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
