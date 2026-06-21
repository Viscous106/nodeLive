"""Admin org schemas — members, role changes, invitations. camelCase JSON."""

from datetime import datetime

from pydantic import EmailStr

from app.models.org import InvitationStatus
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
    status: InvitationStatus
    token: str
    invite_url: str
    created_at: datetime
    expires_at: datetime | None = None


class InvitePreview(CamelModel):
    org_name: str
    email: EmailStr
    role: UserRole


class EnrollmentOut(CamelModel):
    id: str
    user_id: str
    course_id: str
    display_name: str
    email: EmailStr
    course_title: str


class EnrollmentCreate(CamelModel):
    user_id: str
    course_id: str


class SessionStatusCounts(CamelModel):
    scheduled: int
    live: int
    ended: int
    cancelled: int


class OverviewOut(CamelModel):
    total_members: int
    students: int
    instructors: int
    admins: int
    total_courses: int
    total_enrollments: int
    sessions: SessionStatusCounts
    upcoming: list["UpcomingSessionOut"]


class UpcomingSessionOut(CamelModel):
    id: str
    title: str
    scheduled_at: datetime
    duration_mins: int
    status: str
