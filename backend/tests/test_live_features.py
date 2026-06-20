"""M3 live-feature APIs — cue cards, polls, quiz, notices, pinned, bookmarks,
assignment unlock. Socket emits are monkeypatched so the assertions are
deterministic and don't depend on Redis/socket delivery.
"""

from datetime import UTC, datetime

import pytest

from app.auth.security import hash_password
from app.realtime import emit as emit_mod
from app.workers import quiz_tasks as quiz_mod

_PW = "passphrase-1234"


@pytest.fixture
def events(monkeypatch):
    """Capture broadcast events as (event, room, payload) tuples."""
    captured: list = []

    async def cap_session(session_id, event, payload):
        captured.append((event, f"session:{session_id}", payload))

    async def cap_user(session_id, user_id, event, payload):
        captured.append((event, f"session:{session_id}:{user_id}", payload))

    async def cap_instr(session_id, event, payload):
        captured.append((event, f"session:{session_id}:instructor", payload))

    monkeypatch.setattr(emit_mod, "to_session", cap_session)
    monkeypatch.setattr(emit_mod, "to_user", cap_user)
    monkeypatch.setattr(emit_mod, "to_instructors", cap_instr)
    # Don't touch the Celery broker in tests; record the schedule call instead.
    monkeypatch.setattr(
        quiz_mod,
        "schedule_quiz_questions",
        lambda **kw: captured.append(("__scheduled__", "", kw)),
    )
    return captured


def _names(events):
    return [e[0] for e in events]


async def _user(session, email, role="STUDENT"):
    from app.models.user import User, UserRole

    u = User(
        email=email,
        hashed_password=hash_password(_PW),
        display_name=email.split("@")[0],
        role=UserRole(role),
    )
    session.add(u)
    await session.commit()
    return u.id


async def _login(client, email):
    client.cookies.clear()
    await client.post("/api/auth/login", json={"email": email, "password": _PW})


async def _session_row(session, host_id, sid="s1", cid="c1"):
    from app.models.course import ClassSession, Course, SessionStatus

    session.add(Course(id=cid, title="DB"))
    await session.flush()
    session.add(
        ClassSession(
            id=sid,
            course_id=cid,
            host_id=host_id,
            title="Live",
            scheduled_at=datetime(2026, 7, 1, 10, 0, tzinfo=UTC),
            duration_mins=60,
            status=SessionStatus.LIVE,
        )
    )
    await session.commit()


async def _enroll(session, user_id, cid="c1"):
    from app.models.course import Enrollment

    session.add(Enrollment(user_id=user_id, course_id=cid))
    await session.commit()


async def _scenario(client, session):
    """Host instructor + one enrolled student on session s1."""
    host = await _user(session, "host@example.com", role="INSTRUCTOR")
    await _session_row(session, host)
    student = await _user(session, "stu@example.com")
    await _enroll(session, student)
    return host, student


# --- cue cards --------------------------------------------------------------


async def test_cue_card_create_and_show(client, session, events):
    host, _student = await _scenario(client, session)
    await _login(client, "host@example.com")

    r = await client.post(
        "/api/sessions/s1/live/cue-cards",
        json={"content": "Welcome", "displayOrder": 0},
    )
    assert r.status_code == 201
    card_id = r.json()["id"]

    r = await client.patch(f"/api/sessions/s1/live/cue-cards/{card_id}/show")
    assert r.status_code == 200
    assert r.json()["shownAt"] is not None
    assert (
        "cuecard:shown",
        "session:s1",
        {"cardId": card_id, "content": "Welcome", "order": 0},
    ) in events


async def test_cue_card_create_forbidden_for_student(client, session, events):
    _host, _student = await _scenario(client, session)
    await _login(client, "stu@example.com")
    r = await client.post("/api/sessions/s1/live/cue-cards", json={"content": "x"})
    assert r.status_code == 403


# --- polls ------------------------------------------------------------------


async def test_poll_launch_respond_close(client, session, events):
    host, _student = await _scenario(client, session)
    await _login(client, "host@example.com")
    r = await client.post(
        "/api/sessions/s1/live/polls",
        json={"question": "Fav DB?", "options": ["PG", "MySQL"]},
    )
    assert r.status_code == 201
    poll_id = r.json()["id"]
    assert "poll:launched" in _names(events)

    await _login(client, "stu@example.com")
    r = await client.post(
        f"/api/sessions/s1/live/polls/{poll_id}/respond", json={"optionIndex": 0}
    )
    assert r.status_code == 200
    results = r.json()["results"]
    assert results[0] == {"optionIndex": 0, "count": 1, "pct": 100}
    assert "poll:results" in _names(events)

    await _login(client, "host@example.com")
    r = await client.request("DELETE", f"/api/sessions/s1/live/polls/{poll_id}/close")
    assert r.status_code == 200
    assert r.json()["status"] == "CLOSED"
    assert "poll:closed" in _names(events)


async def test_poll_response_is_idempotent_for_points(client, session, events):
    host, _student = await _scenario(client, session)
    await _login(client, "host@example.com")
    poll_id = (
        await client.post(
            "/api/sessions/s1/live/polls", json={"question": "q", "options": ["a", "b"]}
        )
    ).json()["id"]

    await _login(client, "stu@example.com")
    await client.post(
        f"/api/sessions/s1/live/polls/{poll_id}/respond", json={"optionIndex": 0}
    )
    await client.post(
        f"/api/sessions/s1/live/polls/{poll_id}/respond", json={"optionIndex": 1}
    )

    # Re-voting neither double-counts the response nor the +5 participation point.
    state = (await client.get("/api/sessions/s1/live/state")).json()
    assert state["myQuizScore"] == 5


async def test_poll_respond_on_closed_poll_409(client, session, events):
    host, _student = await _scenario(client, session)
    await _login(client, "host@example.com")
    poll_id = (
        await client.post(
            "/api/sessions/s1/live/polls", json={"question": "q", "options": ["a", "b"]}
        )
    ).json()["id"]
    await client.request("DELETE", f"/api/sessions/s1/live/polls/{poll_id}/close")
    await _login(client, "stu@example.com")
    r = await client.post(
        f"/api/sessions/s1/live/polls/{poll_id}/respond", json={"optionIndex": 0}
    )
    assert r.status_code == 409


# --- quiz -------------------------------------------------------------------


async def _make_live_quiz(client):
    quiz_id = (
        await client.post(
            "/api/sessions/s1/live/quiz",
            json={
                "title": "Indexes",
                "timeLimitSecs": 30,
                "questions": [
                    {"text": "2+2?", "options": ["3", "4"], "correctIndex": 1},
                ],
            },
        )
    ).json()["id"]
    await client.post(f"/api/sessions/s1/live/quiz/{quiz_id}/launch")
    return quiz_id


async def test_quiz_create_launch_respond_scores_and_ranks(client, session, events):
    host, _student = await _scenario(client, session)
    await _login(client, "host@example.com")
    quiz_id = await _make_live_quiz(client)
    assert "quiz:launched" in _names(events)
    assert "__scheduled__" in _names(events)

    qid = (await client.get(f"/api/sessions/s1/live/quiz/{quiz_id}/results")).json()[
        "questions"
    ][0]["questionId"]

    await _login(client, "stu@example.com")
    r = await client.post(
        f"/api/sessions/s1/live/quiz/{quiz_id}/respond",
        json={"questionId": qid, "selectedIndex": 1},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["correct"] is True
    assert body["points"] == 10  # answered immediately → full speed bonus
    assert "quiz:score" in _names(events)
    assert "leaderboard:update" in _names(events)


async def test_quiz_wrong_answer_zero_points(client, session, events):
    host, _student = await _scenario(client, session)
    await _login(client, "host@example.com")
    quiz_id = await _make_live_quiz(client)
    qid = (await client.get(f"/api/sessions/s1/live/quiz/{quiz_id}/results")).json()[
        "questions"
    ][0]["questionId"]

    await _login(client, "stu@example.com")
    r = await client.post(
        f"/api/sessions/s1/live/quiz/{quiz_id}/respond",
        json={"questionId": qid, "selectedIndex": 0},
    )
    assert r.json()["points"] == 0


async def test_quiz_double_launch_409(client, session, events):
    host, _student = await _scenario(client, session)
    await _login(client, "host@example.com")
    quiz_id = await _make_live_quiz(client)
    r = await client.post(f"/api/sessions/s1/live/quiz/{quiz_id}/launch")
    assert r.status_code == 409


async def test_quiz_answer_idempotent(client, session, events):
    host, _student = await _scenario(client, session)
    await _login(client, "host@example.com")
    quiz_id = await _make_live_quiz(client)
    qid = (await client.get(f"/api/sessions/s1/live/quiz/{quiz_id}/results")).json()[
        "questions"
    ][0]["questionId"]

    await _login(client, "stu@example.com")
    first = await client.post(
        f"/api/sessions/s1/live/quiz/{quiz_id}/respond",
        json={"questionId": qid, "selectedIndex": 1},
    )
    second = await client.post(
        f"/api/sessions/s1/live/quiz/{quiz_id}/respond",
        json={"questionId": qid, "selectedIndex": 0},  # different answer ignored
    )
    assert second.json()["points"] == first.json()["points"] == 10
    state = (await client.get("/api/sessions/s1/live/state")).json()
    assert state["myQuizScore"] == 10  # not doubled


# --- notices / pinned -------------------------------------------------------


async def test_notice_push_and_dismiss(client, session, events):
    host, _student = await _scenario(client, session)
    await _login(client, "host@example.com")
    r = await client.post(
        "/api/sessions/s1/live/notices", json={"content": "Break", "priority": "NORMAL"}
    )
    assert r.status_code == 201
    notice_id = r.json()["id"]
    assert "notice:pushed" in _names(events)

    r = await client.delete(f"/api/sessions/s1/live/notices/{notice_id}")
    assert r.status_code == 204
    assert "notice:dismissed" in _names(events)


async def test_pinned_message_set_update_unpin(client, session, events):
    host, _student = await _scenario(client, session)
    await _login(client, "host@example.com")
    r = await client.put(
        "/api/sessions/s1/live/pinned-message", json={"message": "Read ch.5"}
    )
    assert r.status_code == 200
    r = await client.put(
        "/api/sessions/s1/live/pinned-message", json={"message": "Read ch.6"}
    )
    assert r.json()["message"] == "Read ch.6"
    state = (await client.get("/api/sessions/s1/live/state")).json()
    assert state["pinnedMessage"] == "Read ch.6"  # upsert, not duplicate
    r = await client.delete("/api/sessions/s1/live/pinned-message")
    assert r.status_code == 204
    assert "message:unpinned" in _names(events)


# --- bookmarks --------------------------------------------------------------


async def test_bookmark_create_and_list(client, session, events):
    _host, _student = await _scenario(client, session)
    await _login(client, "stu@example.com")
    r = await client.post(
        "/api/sessions/s1/live/bookmarks",
        json={"timestampMs": 12000, "label": "key point"},
    )
    assert r.status_code == 201
    r = await client.get("/api/sessions/s1/live/bookmarks")
    assert r.json()[0]["timestampMs"] == 12000


async def test_bookmark_forbidden_for_non_enrolled(client, session, events):
    _host, _student = await _scenario(client, session)
    await _user(session, "outsider@example.com")
    await _login(client, "outsider@example.com")
    r = await client.post("/api/sessions/s1/live/bookmarks", json={"timestampMs": 1})
    assert r.status_code == 403


# --- assignment unlock ------------------------------------------------------


async def test_assignment_unlock_emits_and_sets_timestamp(client, session, events):
    host, _student = await _scenario(client, session)
    from app.models.assignment import Assignment

    session.add(
        Assignment(
            id="a1", course_id="c1", session_id="s1", title="HW1", created_by=host
        )
    )
    await session.commit()

    await _login(client, "host@example.com")
    r = await client.patch("/api/sessions/s1/live/assignments/a1/unlock")
    assert r.status_code == 200
    assert r.json()["unlockedAt"] is not None
    assert "assignment:unlocked" in _names(events)
