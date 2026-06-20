"""Pure attendance helpers (ported from `testing/workers/reconcile.js` +
`testing/routes/webhooks.js`). No DB/IO, so the reconcile rules and the webhook
idempotency key are unit-tested directly — the compliance-critical logic.
"""

from datetime import datetime
from urllib.parse import quote

from app.utils.intervals import merge_intervals


def parse_zoom_time(value: object) -> float | None:
    """Zoom ISO-8601 timestamp (or epoch) → epoch **seconds**, else None."""
    if value is None:
        return None
    if isinstance(value, int | float):
        return float(value)
    if isinstance(value, str):
        s = value.strip()
        if not s:
            return None
        try:
            return datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()
        except ValueError:
            return None
    return None


def encode_meeting_uuid(uuid: str) -> str:
    """URL-encode a meeting UUID for the Reports API path.

    Per Zoom docs, a UUID that begins with '/' or contains '//' must be
    **double** URL-encoded; everything else is encoded once.
    """
    once = quote(uuid, safe="")
    if uuid.startswith("/") or "//" in uuid:
        return quote(once, safe="")
    return once


def build_event_id(event: dict) -> str:
    """Stable idempotency key. Zoom redelivers; many participant events share an
    `event_ts`, so the key includes the meeting UUID + participant UUID too."""
    obj = (event.get("payload") or {}).get("object") or {}
    participant = obj.get("participant") or {}
    return ":".join(
        [
            event.get("event", ""),
            str(event.get("event_ts", "")),
            obj.get("uuid") or "",
            participant.get("participant_uuid") or "",
        ]
    )


def reconcile_participants(participants: list[dict]) -> list[dict]:
    """Group Reports-API participants by identity and union their sessions.

    Identity key = `customer_key` (our app user id) when present, else email,
    else the Zoom-assigned name (last resort). Unioning the join↔leave spans is
    what stops reconnects from double-counting present time. Falls back to
    `duration` (seconds) when `leave_time` is missing.
    """
    groups: dict[str, dict] = {}
    order: list[str] = []

    for p in participants:
        user_id = p.get("customer_key") or None
        email = p.get("user_email") or p.get("email") or None
        name = p.get("name") or p.get("user_name")
        key = user_id or email or f"name:{name}"
        if key not in groups:
            groups[key] = {
                "user_id": user_id,
                "email": email,
                "display_name": name,
                "intervals": [],
            }
            order.append(key)
        g = groups[key]
        g["display_name"] = g["display_name"] or name
        g["user_id"] = g["user_id"] or user_id
        g["email"] = g["email"] or email

        start = parse_zoom_time(p.get("join_time"))
        end = parse_zoom_time(p.get("leave_time"))
        if start is not None and end is not None and end > start:
            g["intervals"].append((start, end))  # epoch seconds
        elif isinstance(p.get("duration"), int | float) and start is not None:
            g["intervals"].append((start, start + float(p["duration"])))

    out: list[dict] = []
    for key in order:
        g = groups[key]
        merged = merge_intervals(g["intervals"])
        present = round(sum(e - s for s, e in merged))
        out.append(
            {
                "user_id": g["user_id"],
                "email": g["email"],
                "display_name": g["display_name"],
                "present_seconds": present,
                "sessions": [[s, e] for s, e in merged],
            }
        )
    return out
