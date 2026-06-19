"""Zoom Meeting SDK signature (ported from testing/server.js generateSignature)."""

import base64
import hashlib
import hmac
import json

from app.utils.zoom_jwt import generate_zoom_signature


def _decode(part: str) -> dict:
    pad = "=" * (-len(part) % 4)
    return json.loads(base64.urlsafe_b64decode(part + pad))


def test_signature_is_three_part_jwt():
    sig = generate_zoom_signature("KEY", "SECRET", "88012345", 0)
    assert sig.count(".") == 2


def test_header_and_payload_claims():
    sig = generate_zoom_signature("KEY", "SECRET", 88012345, 1, now=1000)
    header_b64, payload_b64, _ = sig.split(".")

    header = _decode(header_b64)
    assert header == {"alg": "HS256", "typ": "JWT"}

    payload = _decode(payload_b64)
    assert payload["appKey"] == "KEY"
    assert payload["mn"] == "88012345"  # coerced to string
    assert payload["role"] == 1
    assert payload["iat"] == 1000 - 30
    assert payload["exp"] == 1000 - 30 + 7200
    assert payload["tokenExp"] == payload["exp"]


def test_hmac_signature_verifies_with_secret():
    sig = generate_zoom_signature("KEY", "topsecret", "900", 0, now=2000)
    header_b64, payload_b64, signature = sig.split(".")
    expected = (
        base64.urlsafe_b64encode(
            hmac.new(
                b"topsecret", f"{header_b64}.{payload_b64}".encode(), hashlib.sha256
            ).digest()
        )
        .rstrip(b"=")
        .decode()
    )
    assert signature == expected
