"""Auth dependencies — resolve the current user from the session cookie."""

from fastapi import Cookie, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.tokens import JWTError, decode_token
from app.core.config import settings
from app.db.session import get_db
from app.models.user import User, UserRole

_UNAUTH = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Not authenticated",
    headers={"WWW-Authenticate": "Cookie"},
)


async def get_current_user(
    db: AsyncSession = Depends(get_db),
    session_token: str | None = Cookie(default=None, alias=settings.COOKIE_NAME),
) -> User:
    if not session_token:
        raise _UNAUTH
    try:
        payload = decode_token(session_token)
    except JWTError:
        raise _UNAUTH from None
    user_id = payload.get("sub")
    if not user_id:
        raise _UNAUTH
    user = await db.get(User, user_id)
    if user is None:
        raise _UNAUTH
    return user


def require_role(*roles: UserRole):
    """Dependency factory: 403 unless the current user has one of `roles`."""

    async def _guard(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient role",
            )
        return user

    return _guard
