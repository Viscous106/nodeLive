"""Zoom Meeting SDK signature generation (HS256).

Ported from `testing/server.js` (`generateSignature`). The SDK verifies this
HMAC; the client decodes the JSON claims. `role` is 1 for host, 0 for attendee.
"""

import base64
import hashlib
import hmac
import json
import time


def _b64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def generate_zoom_signature(
    sdk_key: str,
    sdk_secret: str,
    meeting_number: str | int,
    role: int,
    *,
    now: int | None = None,
) -> str:
    iat = int(now if now is not None else time.time()) - 30
    exp = iat + 60 * 60 * 2  # 2 hours

    header = {"alg": "HS256", "typ": "JWT"}
    payload = {
        "appKey": sdk_key,  # sdkKey deprecated since v5 → appKey
        "mn": str(meeting_number),
        "role": role,
        "iat": iat,
        "exp": exp,
        "tokenExp": exp,
    }

    b64_header = _b64url(json.dumps(header, separators=(",", ":")).encode())
    b64_payload = _b64url(json.dumps(payload, separators=(",", ":")).encode())
    message = f"{b64_header}.{b64_payload}"
    signature = _b64url(
        hmac.new(sdk_secret.encode(), message.encode(), hashlib.sha256).digest()
    )
    return f"{message}.{signature}"
