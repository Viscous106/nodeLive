"""Opt-in storage integration test for the R2 (S3-compatible) recording path.

The unit tests cover `pick_mp4` / `is_configured` and the ingest *wiring* behind
seams, but the real boto3 upload + presign + HTTP **Range** (the seeking-works
guarantee) can only be exercised against a live S3-compatible endpoint. This
test does exactly that and is **skipped by default** so CI needs no object store.

Run it against a throwaway MinIO (identical S3 API to R2):

    docker run -d --name it-minio -p 9100:9000 \
      -e MINIO_ROOT_USER=minioadmin -e MINIO_ROOT_PASSWORD=minioadmin \
      minio/minio server /data

    RUN_STORAGE_IT=1 \
    R2_ENDPOINT_URL=http://localhost:9100 R2_ACCESS_KEY_ID=minioadmin \
    R2_SECRET_ACCESS_KEY=minioadmin R2_BUCKET=nodelive-recordings \
    pytest tests/test_recording_storage_integration.py -v

The same command verifies real Cloudflare R2 — just point `R2_*` at the bucket.
"""

import contextlib
import os

import httpx
import pytest

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_STORAGE_IT") != "1",
    reason=(
        "storage integration test — set RUN_STORAGE_IT=1 with R2_* pointing at a "
        "live S3-compatible endpoint (MinIO or Cloudflare R2)"
    ),
)


def _ensure_bucket(client, bucket: str) -> None:
    # Idempotent: already-exists / already-owned is fine.
    with contextlib.suppress(Exception):
        client.create_bucket(Bucket=bucket)


def test_upload_presign_and_range_roundtrip():
    """upload_stream → presign_get → full GET + two Range GETs (seeking)."""
    from app.core.config import settings
    from app.utils import recording_storage as rs

    assert rs.is_configured(), "R2_* env not set for the integration run"
    client = rs._client()
    _ensure_bucket(client, settings.R2_BUCKET)

    # Deterministic 1 MiB stand-in streamed in chunks (exercises multipart reader).
    payload = bytes(range(256)) * 4096
    key = "recordings/it-verify.bin"

    def chunks():
        for i in range(0, len(payload), 64 * 1024):
            yield payload[i : i + 64 * 1024]

    try:
        assert rs.upload_stream(key, chunks(), content_type="video/mp4") == key

        url = rs.presign_get(key, ttl_secs=120)
        full = httpx.get(url)
        assert full.status_code == 200
        assert full.content == payload
        # The CDN/object store must advertise Range support, or seeking breaks.
        assert full.headers.get("accept-ranges") == "bytes"

        # Range at the start and mid-file → 206 Partial Content with exact bytes.
        head = httpx.get(url, headers={"Range": "bytes=0-99"})
        assert head.status_code == 206
        assert head.headers["content-range"] == f"bytes 0-99/{len(payload)}"
        assert head.content == payload[0:100]

        mid = httpx.get(url, headers={"Range": "bytes=524288-524387"})
        assert mid.status_code == 206
        assert mid.content == payload[524288:524388]
    finally:
        client.delete_object(Bucket=settings.R2_BUCKET, Key=key)


def test_ingest_streams_real_object_to_store():
    """run_ingest with the REAL boto3 upload (only the Zoom fetch + DB mark
    are injected) lands the bytes in the store under recordings/<uuid>.mp4."""
    import asyncio

    from app.core.config import settings
    from app.utils import recording_storage as rs
    from app.workers.recording_tasks import run_ingest

    client = rs._client()
    _ensure_bucket(client, settings.R2_BUCKET)

    payload = bytes(range(256)) * 2048  # 512 KiB
    marks: list = []

    async def fake_zoom_stream(url):
        assert "access_token=dl-tok" in url  # download_token preferred
        for i in range(0, len(payload), 128 * 1024):
            yield payload[i : i + 128 * 1024]

    async def capture_mark(uuid, key, status, duration):
        marks.append((status, key, duration))

    files = [
        {
            "file_type": "MP4",
            "recording_type": "shared_screen_with_speaker_view",
            "download_url": "https://zoom.us/rec/x.mp4",
            "recording_start": "2026-06-21T10:00:00Z",
            "recording_end": "2026-06-21T10:50:00Z",  # 3000s
        }
    ]

    key = asyncio.run(
        run_ingest(
            "it-ingest-1",
            "dl-tok",
            files,
            http_get_stream=fake_zoom_stream,
            mark=capture_mark,
        )
    )
    try:
        assert key == "recordings/it-ingest-1.mp4"
        body = client.get_object(Bucket=settings.R2_BUCKET, Key=key)["Body"].read()
        assert body == payload
        assert marks == [("stored", "recordings/it-ingest-1.mp4", 3000)]
    finally:
        client.delete_object(Bucket=settings.R2_BUCKET, Key=key)
