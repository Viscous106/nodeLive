"""JWT access tokens — HS256, signed with AUTH_SECRET.

The token's `sub` claim is the user id. Tokens are carried in an HttpOnly
session cookie (see `app.api.auth`).
"""

from datetime import UTC, datetime, timedelta

from jose import JWTError, jwt

from app.core.config import settings

ALGORITHM = "HS256"


def create_access_token(subject: str) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": subject,
        "iat": now,
        "exp": now + timedelta(minutes=settings.ACCESS_TOKEN_TTL_MINUTES),
    }
    return jwt.encode(payload, settings.AUTH_SECRET, algorithm=ALGORITHM)


def decode_token(token: str) -> dict:
    """Decode + verify a token. Raises `jose.JWTError` if invalid/expired."""
    return jwt.decode(token, settings.AUTH_SECRET, algorithms=[ALGORITHM])


__all__ = ["create_access_token", "decode_token", "JWTError"]
