"""Live caption buffer in Redis — recent transcript for the AI assistant.

A per-session sorted set keyed by timestamp, trimmed to the most recent N lines
so the AI context stays bounded.
"""

CAPTION_CAP = 50


def caption_key(session_id: str) -> str:
    return f"captions:{session_id}"


async def buffer_caption(
    redis, session_id: str, text: str, timestamp: float, cap: int = CAPTION_CAP
) -> None:
    key = caption_key(session_id)
    # Member encodes the timestamp so identical text at different times is kept.
    await redis.zadd(key, {f"{timestamp}|{text}": float(timestamp)})
    await redis.zremrangebyrank(key, 0, -(cap + 1))


async def get_captions(redis, session_id: str) -> list[str]:
    members = await redis.zrange(caption_key(session_id), 0, -1)
    return [m.split("|", 1)[1] for m in members]
