"""PATCH /api/auth/me — profile update."""

import pytest


async def _signup(client, email="user@example.com", password="pass1234"):
    r = await client.post(
        "/api/auth/signup",
        json={"email": email, "password": password, "displayName": "Original Name"},
    )
    assert r.status_code == 201
    return r.json()


@pytest.mark.asyncio
async def test_update_display_name(client):
    await _signup(client)
    r = await client.patch("/api/auth/me", json={"displayName": "New Name"})
    assert r.status_code == 200
    assert r.json()["displayName"] == "New Name"


@pytest.mark.asyncio
async def test_update_avatar_url(client):
    await _signup(client)
    r = await client.patch(
        "/api/auth/me", json={"avatarUrl": "https://example.com/avatar.png"}
    )
    assert r.status_code == 200
    assert r.json()["avatarUrl"] == "https://example.com/avatar.png"


@pytest.mark.asyncio
async def test_update_both_fields(client):
    await _signup(client)
    r = await client.patch(
        "/api/auth/me",
        json={"displayName": "Combined", "avatarUrl": "https://example.com/pic.jpg"},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["displayName"] == "Combined"
    assert data["avatarUrl"] == "https://example.com/pic.jpg"


@pytest.mark.asyncio
async def test_empty_patch_is_no_op(client):
    await _signup(client)
    r = await client.patch("/api/auth/me", json={})
    assert r.status_code == 200
    assert r.json()["displayName"] == "Original Name"


@pytest.mark.asyncio
async def test_patch_me_requires_auth(client):
    client.cookies.clear()
    r = await client.patch("/api/auth/me", json={"displayName": "Hacker"})
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_blank_display_name_rejected(client):
    await _signup(client)
    r = await client.patch("/api/auth/me", json={"displayName": "   "})
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_non_http_avatar_url_rejected(client):
    await _signup(client)
    r = await client.patch(
        "/api/auth/me", json={"avatarUrl": "javascript:alert(1)"}
    )
    assert r.status_code == 422
