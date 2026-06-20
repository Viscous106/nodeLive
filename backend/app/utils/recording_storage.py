"""Cloudflare R2 (S3-compatible) storage for class recordings.

boto3 is sync; the API presigns inside a threadpool-friendly call and the
Celery ingest task is sync anyway. Everything raises `RuntimeError` when R2 is
unconfigured so callers can map that to a 501 / failed-ingest.
"""

from collections.abc import Iterator

import boto3
from botocore.config import Config

from app.core.config import settings

_MP4 = "MP4"
_PREFERRED = "shared_screen_with_speaker_view"


def is_configured() -> bool:
    return all(
        (
            settings.R2_BUCKET,
            settings.R2_ENDPOINT_URL,
            settings.R2_ACCESS_KEY_ID,
            settings.R2_SECRET_ACCESS_KEY,
        )
    )


def pick_mp4(recording_files: list[dict] | None) -> dict | None:
    """Speaker-view MP4 if present, else any MP4, else None."""
    mp4s = [
        f for f in (recording_files or []) if (f.get("file_type") or "").upper() == _MP4
    ]
    if not mp4s:
        return None
    for f in mp4s:
        if f.get("recording_type") == _PREFERRED:
            return f
    return mp4s[0]


def _client():
    if not is_configured():
        raise RuntimeError("R2 storage is not configured")
    return boto3.client(
        "s3",
        endpoint_url=settings.R2_ENDPOINT_URL,
        aws_access_key_id=settings.R2_ACCESS_KEY_ID,
        aws_secret_access_key=settings.R2_SECRET_ACCESS_KEY,
        region_name="auto",
        config=Config(signature_version="s3v4"),
    )


def upload_stream(
    key: str, body: Iterator[bytes], content_type: str = "video/mp4"
) -> str:
    """Stream an iterator of bytes to R2 via the managed multipart uploader."""
    client = _client()

    class _Reader:
        def __init__(self, it: Iterator[bytes]):
            self._it = it
            self._buf = b""

        def read(self, n: int = -1) -> bytes:
            if n is None or n < 0:
                chunks = [self._buf, *self._it]
                self._buf = b""
                return b"".join(chunks)
            while len(self._buf) < n:
                try:
                    self._buf += next(self._it)
                except StopIteration:
                    break
            out, self._buf = self._buf[:n], self._buf[n:]
            return out

    client.upload_fileobj(
        _Reader(body),
        settings.R2_BUCKET,
        key,
        ExtraArgs={"ContentType": content_type},
    )
    return key


def presign_get(key: str, ttl_secs: int | None = None) -> str:
    """Short-lived presigned GET URL (works on R2 and AWS S3)."""
    client = _client()
    return client.generate_presigned_url(
        "get_object",
        Params={"Bucket": settings.R2_BUCKET, "Key": key},
        ExpiresIn=ttl_secs or settings.RECORDING_URL_TTL_SECS,
    )
