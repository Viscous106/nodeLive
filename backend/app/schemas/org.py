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
