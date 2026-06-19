"""Resolve the connecting user from the session cookie on a socket handshake."""

from http.cookies import SimpleCookie

from app.auth.tokens import JWTError, decode_token
from app.core.config import settings


def resolve_user_id_from_environ(environ: dict) -> str | None:
    """Return the user id from the auth cookie in a socket.io `environ`, or None.

    The cookie carries the same HS256 JWT as the HTTP API (see app.auth).
    """
    raw_cookie = environ.get("HTTP_COOKIE", "")
    if not raw_cookie:
        return None
    jar = SimpleCookie()
    jar.load(raw_cookie)
    morsel = jar.get(settings.COOKIE_NAME)
    if morsel is None:
        return None
    try:
        payload = decode_token(morsel.value)
    except JWTError:
        return None
    sub = payload.get("sub")
    return sub if isinstance(sub, str) else None
