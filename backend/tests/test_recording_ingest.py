"""Recording ingest: MP4 selection, the 501 gate, and the ingest seam wiring."""

import asyncio

from app.utils.recording_storage import is_configured, pick_mp4
from app.workers.recording_tasks import run_ingest


def test_pick_mp4_prefers_speaker_view():
    files = [
        {"file_type": "MP4", "recording_type": "audio_only", "id": "a"},
        {
            "file_type": "MP4",
            "recording_type": "shared_screen_with_speaker_view",
            "id": "b",
        },
        {"file_type": "M4A", "recording_type": "audio_only", "id": "c"},
    ]
    assert pick_mp4(files)["id"] == "b"


def test_pick_mp4_falls_back_to_any_mp4():
    files = [{"file_type": "MP4", "recording_type": "gallery_view", "id": "g"}]
    assert pick_mp4(files)["id"] == "g"


def test_pick_mp4_none_when_no_mp4():
    assert pick_mp4([{"file_type": "M4A", "id": "x"}]) is None
    assert pick_mp4([]) is None


def test_is_configured_false_without_creds(monkeypatch):
    from app.core import config

    for attr in (
        "R2_BUCKET",
        "R2_ENDPOINT_URL",
        "R2_ACCESS_KEY_ID",
        "R2_SECRET_ACCESS_KEY",
    ):
        monkeypatch.setattr(config.settings, attr, "")
    assert is_configured() is False


def _run(coro):
    return asyncio.run(coro)


def test_ingest_prefers_download_token_and_marks_stored():
    calls = {}

    async def get_token():
        calls["token_fetched"] = True
        return "s2s-token"

    async def http_get_stream(url):
        calls["url"] = url
        yield b"abc"
        yield b"def"

    async def upload(key, body):
        calls["key"] = key
        calls["bytes"] = (
            b"".join([c async for c in body]) if hasattr(body, "__aiter__") else None
        )
        return key

    async def mark(uuid, key, status, duration):
        calls["mark"] = (uuid, key, status, duration)

    files = [
        {
            "file_type": "MP4",
            "recording_type": "shared_screen_with_speaker_view",
            "download_url": "https://zoom.us/rec/abc.mp4",
            "recording_start": "2026-06-20T10:00:00Z",
            "recording_end": "2026-06-20T11:00:00Z",
        }
    ]

    key = _run(
        run_ingest(
            "uuid-1",
            "dl-token",
            files,
            get_token=get_token,
            http_get_stream=http_get_stream,
            upload=upload,
            mark=mark,
        )
    )

    assert key == "recordings/uuid-1.mp4"
    # download_token preferred → S2S token never fetched
    assert "token_fetched" not in calls
    assert "access_token=dl-token" in calls["url"]
    assert calls["mark"] == ("uuid-1", "recordings/uuid-1.mp4", "stored", 3600)


def test_ingest_falls_back_to_s2s_when_no_download_token():
    async def get_token():
        return "s2s-token"

    async def http_get_stream(url):
        assert "access_token=s2s-token" in url
        yield b"x"

    async def upload(key, body):
        async for _ in body:
            pass
        return key

    marks = []

    async def mark(uuid, key, status, duration):
        marks.append((status, key))

    files = [
        {
            "file_type": "MP4",
            "recording_type": "gallery_view",
            "download_url": "https://zoom.us/rec/g.mp4",
        }
    ]
    _run(
        run_ingest(
            "u2",
            None,
            files,
            get_token=get_token,
            http_get_stream=http_get_stream,
            upload=upload,
            mark=mark,
        )
    )
    assert marks[-1][0] == "stored"


def test_ingest_marks_failed_when_no_mp4():
    marks = []

    async def mark(uuid, key, status, duration):
        marks.append((status, key))

    async def boom(*a, **k):  # must not be reached
        raise AssertionError("should not download")

    try:
        _run(
            run_ingest(
                "u3",
                "t",
                [{"file_type": "M4A"}],
                get_token=boom,
                http_get_stream=boom,
                upload=boom,
                mark=mark,
            )
        )
        raise AssertionError("expected ValueError")
    except ValueError:
        pass
    assert marks == [("failed", None)]
