"""AD — admin Members & Roles surface: list, promote (last-admin guard),
invitations (create link / list / revoke) + public invite preview.

All `/api/admin/*` routes are `require_org_role(ADMIN)`-gated; the preview at
`/api/invitations/{token}` is public (the signup screen reads it).
"""

from sqlalchemy import select

from app.auth.security import hash_password
from app.models.org import Invitation, InvitationStatus, Membership
from app.models.user import User, UserRole
from app.services.roles import assign_role

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
    await assign_role(session, u, role)  # membership + mirror
    await session.commit()
    return u


async def _login(client, email):
    client.cookies.clear()
    r = await client.post("/api/auth/login", json={"email": email, "password": _PW})
    assert r.status_code == 200, r.text


# --- members list + role gating ----------------------------------------------


async def test_admin_lists_members(client, session):
    await _user(session, "admin@x.com", UserRole.ADMIN)
    await _user(session, "stu@x.com", UserRole.STUDENT)
    await _login(client, "admin@x.com")

    r = await client.get("/api/admin/members")
    assert r.status_code == 200
    members = {m["email"]: m for m in r.json()}
    assert members.keys() == {"admin@x.com", "stu@x.com"}
    assert members["admin@x.com"]["role"] == "ADMIN"
    assert members["stu@x.com"]["role"] == "STUDENT"
    assert "joinedAt" in members["stu@x.com"]
    assert "userId" in members["stu@x.com"]


async def test_non_admin_cannot_list_members(client, session):
    await _user(session, "admin@x.com", UserRole.ADMIN)
    await _user(session, "stu@x.com", UserRole.STUDENT)
    await _login(client, "stu@x.com")
    assert (await client.get("/api/admin/members")).status_code == 403


async def test_unauthenticated_cannot_list_members(client, session):
    await _user(session, "admin@x.com", UserRole.ADMIN)
    client.cookies.clear()
    assert (await client.get("/api/admin/members")).status_code == 401


# --- promote / demote ---------------------------------------------------------


async def test_admin_promotes_student_to_instructor(client, session):
    await _user(session, "admin@x.com", UserRole.ADMIN)
    stu = await _user(session, "stu@x.com", UserRole.STUDENT)
    await _login(client, "admin@x.com")

    r = await client.patch(
        f"/api/admin/members/{stu.id}/role", json={"role": "INSTRUCTOR"}
    )
    assert r.status_code == 200
    assert r.json()["role"] == "INSTRUCTOR"

    # membership + the User.role mirror both updated
    m = await session.scalar(select(Membership).where(Membership.user_id == stu.id))
    await session.refresh(stu)
    assert m.role == UserRole.INSTRUCTOR
    assert stu.role == UserRole.INSTRUCTOR


async def test_cannot_demote_last_admin(client, session):
    admin = await _user(session, "admin@x.com", UserRole.ADMIN)
    await _login(client, "admin@x.com")
    r = await client.patch(
        f"/api/admin/members/{admin.id}/role", json={"role": "STUDENT"}
    )
    assert r.status_code == 409


async def test_can_demote_admin_when_another_admin_exists(client, session):
    await _user(session, "admin@x.com", UserRole.ADMIN)
    admin2 = await _user(session, "admin2@x.com", UserRole.ADMIN)
    await _login(client, "admin@x.com")
    r = await client.patch(
        f"/api/admin/members/{admin2.id}/role", json={"role": "STUDENT"}
    )
    assert r.status_code == 200
    assert r.json()["role"] == "STUDENT"


async def test_promote_unknown_user_404(client, session):
    await _user(session, "admin@x.com", UserRole.ADMIN)
    await _login(client, "admin@x.com")
    r = await client.patch("/api/admin/members/nope/role", json={"role": "INSTRUCTOR"})
    assert r.status_code == 404


# --- invitations + public preview --------------------------------------------


async def test_create_invitation_and_public_preview(client, session):
    await _user(session, "admin@x.com", UserRole.ADMIN)
    await _login(client, "admin@x.com")

    r = await client.post(
        "/api/admin/invitations",
        json={"email": "prof@uni.edu", "role": "INSTRUCTOR"},
    )
    assert r.status_code == 201
    body = r.json()
    assert body["email"] == "prof@uni.edu"
    assert body["role"] == "INSTRUCTOR"
    assert body["status"] == "PENDING"
    token = body["token"]
    assert token and body["inviteUrl"].endswith(token)

    # public preview — no auth
    client.cookies.clear()
    p = await client.get(f"/api/invitations/{token}")
    assert p.status_code == 200
    assert p.json() == {
        "orgName": "linkHQ",
        "email": "prof@uni.edu",
        "role": "INSTRUCTOR",
    }


async def test_invite_existing_member_conflicts(client, session):
    await _user(session, "admin@x.com", UserRole.ADMIN)
    await _user(session, "already@x.com", UserRole.STUDENT)
    await _login(client, "admin@x.com")
    r = await client.post(
        "/api/admin/invitations", json={"email": "already@x.com", "role": "INSTRUCTOR"}
    )
    assert r.status_code == 409


async def test_list_and_revoke_invitations(client, session):
    await _user(session, "admin@x.com", UserRole.ADMIN)
    await _login(client, "admin@x.com")
    await client.post(
        "/api/admin/invitations", json={"email": "a@uni.edu", "role": "INSTRUCTOR"}
    )

    listed = (await client.get("/api/admin/invitations")).json()
    assert len(listed) == 1
    inv_id = listed[0]["id"]

    assert (await client.delete(f"/api/admin/invitations/{inv_id}")).status_code == 204
    # revoked invitations drop out of the pending list
    assert (await client.get("/api/admin/invitations")).json() == []
    inv = await session.scalar(select(Invitation).where(Invitation.id == inv_id))
    assert inv.status == InvitationStatus.REVOKED


async def test_public_preview_rejects_unknown_token(client, session):
    client.cookies.clear()
    assert (await client.get("/api/invitations/does-not-exist")).status_code == 404


async def test_non_admin_cannot_invite(client, session):
    await _user(session, "stu@x.com", UserRole.STUDENT)
    await _login(client, "stu@x.com")
    r = await client.post(
        "/api/admin/invitations", json={"email": "x@uni.edu", "role": "INSTRUCTOR"}
    )
    assert r.status_code == 403
