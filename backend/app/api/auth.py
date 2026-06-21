"""Auth routes: signup, login, logout, current user.

Identity lives in an HttpOnly session cookie carrying a short-lived JWT.
"""

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import get_current_user
from app.auth.security import hash_password, verify_password
from app.auth.tokens import create_access_token
from app.core.config import settings
from app.db.session import get_db
from app.models.org import Invitation, InvitationStatus
from app.models.user import User, UserRole
from app.schemas.auth import LoginIn, ProfileUpdate, SignupIn, UserOut
from app.services.enrollment import ensure_enrolled_all_courses
from app.services.roles import assign_role, maybe_bootstrap_admin

router = APIRouter(prefix="/auth", tags=["auth"])


def _set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=settings.COOKIE_NAME,
        value=token,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite="strict",
        max_age=settings.ACCESS_TOKEN_TTL_MINUTES * 60,
        path="/",
    )


async def _resolve_invite(db: AsyncSession, token: str, email: str) -> Invitation:
    """Validate an invite token against the signup email (email-locked).

    A shareable link, but only the invited email may accept it.
    """
    invite = await db.scalar(select(Invitation).where(Invitation.token == token))
    bad = HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired invitation"
    )
    if invite is None or invite.status is not InvitationStatus.PENDING:
        raise bad
    if invite.expires_at is not None and invite.expires_at < datetime.now(UTC):
        raise bad
    if invite.email.lower() != email.lower():
        raise bad
    return invite


@router.post("/signup", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def signup(
    body: SignupIn,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> User:
    existing = await db.scalar(select(User).where(User.email == body.email))
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )

    invite = (
        await _resolve_invite(db, body.invite_token, body.email)
        if body.invite_token
        else None
    )
    role = invite.role if invite else UserRole.STUDENT

    user = User(
        email=body.email,
        hashed_password=hash_password(body.password),
        display_name=body.display_name,
    )
    db.add(user)
    await db.flush()
    # One service writes membership + the User.role mirror together.
    await assign_role(db, user, role)
    if invite is not None:
        invite.status = InvitationStatus.ACCEPTED
        invite.accepted_at = datetime.now(UTC)
    # A bootstrap-admin email outranks the default/invited role.
    await maybe_bootstrap_admin(db, user)
    # Single-org: everyone is enrolled in every course (dashboard visibility).
    await ensure_enrolled_all_courses(db, user)
    await db.commit()
    await db.refresh(user)
    _set_session_cookie(response, create_access_token(user.id))
    return user


@router.post("/login", response_model=UserOut)
async def login(
    body: LoginIn,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> User:
    user = await db.scalar(select(User).where(User.email == body.email))
    if user is None or not verify_password(body.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    # Promote a configured bootstrap-admin on login (no-shell first admin).
    if await maybe_bootstrap_admin(db, user):
        await db.commit()
    _set_session_cookie(response, create_access_token(user.id))
    return user


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(response: Response) -> None:
    response.delete_cookie(settings.COOKIE_NAME, path="/")


@router.get("/me", response_model=UserOut)
async def me(user: User = Depends(get_current_user)) -> User:
    return user


@router.patch("/me", response_model=UserOut)
async def update_me(
    body: ProfileUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> User:
    if body.display_name is not None:
        name = body.display_name.strip()
        if not name:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="display_name cannot be blank",
            )
        user.display_name = name
    if body.avatar_url is not None:
        user.avatar_url = body.avatar_url
    await db.commit()
    await db.refresh(user)
    return user
