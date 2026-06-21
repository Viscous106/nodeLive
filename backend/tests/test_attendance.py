"""Pure attendance reconcile logic (union + identity match + duration fallback),
the UUID encoder, the idempotency-key builder, and the reconcile wiring via its
injection seam. No DB/IO — the compliance-critical core, tested offline.
"""

import httpx
import pytest

from app.utils.attendance import (
    build_event_id,
    encode_meeting_uuid,
    reconcile_participants,
)
from app.workers.attendance_tasks import run_reconcile

_DAY = "2026-06-20"


def _p(**kw):
    return kw


# --- union / double-count prevention ----------------------------------------


def test_reconnect_spans_are_unioned_not_summed():
    # Same user, two OVERLAPPING spans (a reconnect) → counted once.
    parts = [
        _p(
            customer_key="u1",
            name="A",
            join_time=f"{_DAY}T10:00:00Z",
            leave_time=f"{_DAY}T10:30:00Z",
        ),
        _p(
            customer_key="u1",
            name="A",
            join_time=f"{_DAY}T10:20:00Z",
            leave_time=f"{_DAY}T10:50:00Z",
        ),
    ]
    [row] = reconcile_participants(parts)
    assert row["user_id"] == "u1"
    assert row["present_seconds"] == 50 * 60  # 10:00–10:50, not 60 min


def test_disjoint_spans_sum():
    parts = [
        _p(
            customer_key="u1",
            name="A",
            join_time=f"{_DAY}T10:00:00Z",
            leave_time=f"{_DAY}T10:30:00Z",
        ),
        _p(
            customer_key="u1",
            name="A",
            join_time=f"{_DAY}T10:40:00Z",
            leave_time=f"{_DAY}T11:00:00Z",
        ),
    ]
    [row] = reconcile_participants(parts)
    assert row["present_seconds"] == 50 * 60  # 30 + 20


# --- identity matching: customer_key → email → name -------------------------


def test_identity_prefers_customer_key_over_email():
    # Same app user joining from two different emails → one group keyed by id.
    parts = [
        _p(
            customer_key="u1",
            user_email="a@x.com",
            join_time=f"{_DAY}T10:00:00Z",
            leave_time=f"{_DAY}T10:10:00Z",
        ),
        _p(
            customer_key="u1",
            user_email="b@x.com",
            join_time=f"{_DAY}T10:10:00Z",
            leave_time=f"{_DAY}T10:20:00Z",
        ),
    ]
    rows = reconcile_participants(parts)
    assert len(rows) == 1
    assert rows[0]["present_seconds"] == 20 * 60


def test_identity_falls_back_to_email_then_name():
    parts = [
        _p(
            user_email="guest@x.com",
            name="Guest",
            join_time=f"{_DAY}T10:00:00Z",
            leave_time=f"{_DAY}T10:05:00Z",
        ),
        _p(
            name="NoEmail",
            join_time=f"{_DAY}T10:00:00Z",
            leave_time=f"{_DAY}T10:05:00Z",
        ),
    ]
    rows = reconcile_participants(parts)
    assert {r["email"] for r in rows} == {"guest@x.com", None}
    assert len(rows) == 2  # different identities, not merged


def test_duration_fallback_when_leave_time_missing():
    parts = [
        _p(customer_key="u1", name="A", join_time=f"{_DAY}T10:00:00Z", duration=600)
    ]
    [row] = reconcile_participants(parts)
    assert row["present_seconds"] == 600


# --- UUID encoding ----------------------------------------------------------


def test_encode_uuid_single_for_normal():
    assert encode_meeting_uuid("abc123==") == "abc123%3D%3D"


def test_encode_uuid_double_when_leading_slash_or_double_slash():
    # Leading '/' and '//' both force a second encode pass.
    assert encode_meeting_uuid("/abc==") == encode_meeting_uuid_double("/abc==")
    assert "%252F" in encode_meeting_uuid("a//b")


def encode_meeting_uuid_double(uuid):
    from urllib.parse import quote

    return quote(quote(uuid, safe=""), safe="")


# --- idempotency key --------------------------------------------------------


def test_event_id_is_composite():
    event = {
        "event": "meeting.participant_joined",
        "event_ts": 123,
        "payload": {
            "object": {"uuid": "U1", "participant": {"participant_uuid": "P1"}}
        },
    }
    assert build_event_id(event) == "meeting.participant_joined:123:U1:P1"


def test_event_id_distinguishes_participants_sharing_a_timestamp():
    base = {"event": "meeting.participant_joined", "event_ts": 123}
    a = build_event_id(
        {
            **base,
            "payload": {
                "object": {"uuid": "U1", "participant": {"participant_uuid": "P1"}}
            },
        }
    )
    b = build_event_id(
        {
            **base,
            "payload": {
                "object": {"uuid": "U1", "participant": {"participant_uuid": "P2"}}
            },
        }
    )
    assert a != b  # same ts must not collapse distinct joins


# --- reconcile wiring (injection seam) --------------------------------------


async def test_run_reconcile_paginates_and_writes():
    pages = [
        {
            "participants": [
                _p(
                    customer_key="u1",
                    name="A",
                    join_time=f"{_DAY}T10:00:00Z",
                    leave_time=f"{_DAY}T10:30:00Z",
                )
            ],
            "next_page_token": "page2",
        },
        {
            "participants": [
                _p(
                    customer_key="u1",
                    name="A",
                    join_time=f"{_DAY}T10:40:00Z",
                    leave_time=f"{_DAY}T11:00:00Z",
                )
            ],
            "next_page_token": "",
        },
    ]
    seen_urls = []

    async def fake_token():
        return "tok"

    async def fake_get(url, token):
        seen_urls.append(url)
        return pages[len(seen_urls) - 1]

    captured = {}

    async def fake_write(uuid, finals):
        captured["uuid"] = uuid
        captured["finals"] = finals

    n = await run_reconcile(
        "/recurring==", get_token=fake_token, http_get=fake_get, write=fake_write
    )
    assert n == 1
    assert len(seen_urls) == 2  # followed next_page_token
    assert "page2" in seen_urls[1]
    final = captured["finals"][0]
    assert final["user_id"] == "u1"
    assert final["present_seconds"] == 50 * 60  # both spans unioned across pages


@pytest.mark.asyncio
async def test_reconcile_falls_back_to_past_meetings_on_scope_error():
    """When the Reports API is rejected for scope/plan (4xx), reconcile retries
    against /past_meetings (lighter scope), so attendance still computes."""
    seen_urls: list[str] = []

    async def fake_token():
        return "tok"

    async def fake_get(url, token):
        seen_urls.append(url)
        if "/report/meetings/" in url:
            req = httpx.Request("GET", url)
            resp = httpx.Response(400, text="missing scope", request=req)
            raise httpx.HTTPStatusError("scope", request=req, response=resp)
        return {
            "participants": [
                _p(
                    email="a@x.com",
                    name="A",
                    join_time=f"{_DAY}T10:00:00Z",
                    leave_time=f"{_DAY}T10:30:00Z",
                )
            ],
            "next_page_token": "",
        }

    captured = {}

    async def fake_write(uuid, finals):
        captured["finals"] = finals

    n = await run_reconcile(
        "abc==", get_token=fake_token, http_get=fake_get, write=fake_write
    )
    assert n == 1
    assert any("/report/meetings/" in u for u in seen_urls)  # tried report first
    assert any("/past_meetings/" in u for u in seen_urls)  # then fell back
    assert captured["finals"][0]["present_seconds"] == 30 * 60
