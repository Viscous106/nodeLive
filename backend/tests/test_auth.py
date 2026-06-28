"""Auth route behavior — signup, login, logout, current user."""


async def test_signup_creates_user_and_sets_cookie(client):
    resp = await client.post(
        "/api/auth/signup",
        json={
            "email": "ada@example.com",
            "password": "correct horse battery",
            "displayName": "Ada Lovelace",
        },
    )

    assert resp.status_code == 201
    body = resp.json()
    assert body["email"] == "ada@example.com"
    assert body["displayName"] == "Ada Lovelace"
    assert body["role"] == "STUDENT"
    assert body["coins"] == 0
    assert "id" in body
    assert "password" not in body
    assert "hashedPassword" not in body
    # session cookie is set so the client is authenticated immediately
    assert "nodelive_session" in resp.cookies


async def test_signup_rejects_duplicate_email(client):
    payload = {
        "email": "dup@example.com",
        "password": "passphrase one",
        "displayName": "First",
    }
    first = await client.post("/api/auth/signup", json=payload)
    assert first.status_code == 201

    second = await client.post("/api/auth/signup", json=payload)
    assert second.status_code == 409


async def _signup(client, email="grace@example.com", password="hopper rocks"):
    return await client.post(
        "/api/auth/signup",
        json={"email": email, "password": password, "displayName": "Grace"},
    )


async def test_login_with_correct_password_succeeds(client):
    await _signup(client)
    client.cookies.clear()  # forget the signup session

    resp = await client.post(
        "/api/auth/login",
        json={"email": "grace@example.com", "password": "hopper rocks"},
    )

    assert resp.status_code == 200
    assert resp.json()["email"] == "grace@example.com"
    assert "nodelive_session" in resp.cookies


async def test_login_with_wrong_password_is_401(client):
    await _signup(client)
    client.cookies.clear()

    resp = await client.post(
        "/api/auth/login",
        json={"email": "grace@example.com", "password": "wrong"},
    )

    assert resp.status_code == 401
    assert "nodelive_session" not in resp.cookies


async def test_login_unknown_email_is_401(client):
    resp = await client.post(
        "/api/auth/login",
        json={"email": "nobody@example.com", "password": "whatever"},
    )
    assert resp.status_code == 401


async def test_me_returns_current_user_when_authenticated(client):
    await _signup(client)  # leaves the session cookie on the client

    resp = await client.get("/api/auth/me")

    assert resp.status_code == 200
    assert resp.json()["email"] == "grace@example.com"


async def test_me_without_cookie_is_401(client):
    resp = await client.get("/api/auth/me")
    assert resp.status_code == 401


async def test_logout_clears_session_cookie(client):
    await _signup(client)

    resp = await client.post("/api/auth/logout")
    assert resp.status_code == 204

    # cookie cleared → /me now unauthorized
    client.cookies.clear()
    me = await client.get("/api/auth/me")
    assert me.status_code == 401
