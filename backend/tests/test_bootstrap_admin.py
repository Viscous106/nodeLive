"""No-shell first-admin bootstrap: a configured email auto-becomes ADMIN on
login/signup so the admin panel is usable on a deployed instance without shell
access to run `set_role`. Default allowlist includes abhinav.singh@scaler.com.
"""

from sqlalchemy import select

from app.auth.security import hash_password
from app.models.org import Membership
from app.models.user import User, UserRole

_PW = "passphrase-1234"
_ADMIN_EMAIL = "abhinav.singh@scaler.com"


async def test_login_promotes_existing_bootstrap_user_to_admin(client, session):
    u = User(
        email=_ADMIN_EMAIL,
        hashed_password=hash_password(_PW),
        display_name="Abhinav",
        role=UserRole.STUDENT,
    )
    session.add(u)
    await session.commit()

    r = await client.post(
        "/api/auth/login", json={"email": _ADMIN_EMAIL, "password": _PW}
    )
    assert r.status_code == 200
    assert r.json()["role"] == "ADMIN"

    await session.refresh(u)
    assert u.role is UserRole.ADMIN  # mirror promoted
    m = await session.scalar(select(Membership).where(Membership.user_id == u.id))
    assert m.role is UserRole.ADMIN  # membership promoted


async def test_signup_with_bootstrap_email_is_admin(client, session):
    r = await client.post(
        "/api/auth/signup",
        json={"email": _ADMIN_EMAIL, "password": _PW, "displayName": "Abhinav"},
    )
    assert r.status_code == 201
    assert r.json()["role"] == "ADMIN"


async def test_bootstrap_is_case_insensitive(client, session):
    r = await client.post(
        "/api/auth/signup",
        json={
            "email": _ADMIN_EMAIL.upper(),
            "password": _PW,
            "displayName": "Abhinav",
        },
    )
    assert r.status_code == 201
    assert r.json()["role"] == "ADMIN"


async def test_regular_user_login_not_promoted(client, session):
    u = User(
        email="someone@x.com",
        hashed_password=hash_password(_PW),
        display_name="Someone",
        role=UserRole.STUDENT,
    )
    session.add(u)
    await session.commit()
    r = await client.post(
        "/api/auth/login", json={"email": "someone@x.com", "password": _PW}
    )
    assert r.status_code == 200
    assert r.json()["role"] == "STUDENT"
