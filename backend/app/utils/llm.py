"""LLM provider wrapper — Anthropic primary, Groq (OpenAI-compatible) fallback.

Streaming text chat for the live AI chat (and future post-meeting AI). The
provider is chosen at call time: Anthropic when `ANTHROPIC_API_KEY` is set, else
Groq when `GROQ_API_KEY` is set, else `is_configured()` is False and callers
should return 501. Groq speaks the OpenAI chat-completions SSE protocol, so its
stream is parsed from `httpx` (no extra SDK). See plan.md §7.4a.
"""

import json
from collections.abc import AsyncIterator

import httpx

from app.core.config import settings

_GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
_MAX_TOKENS = 1024


def is_configured() -> bool:
    """True if any LLM provider key is set (Anthropic or Groq)."""
    return bool(settings.ANTHROPIC_API_KEY or settings.GROQ_API_KEY)


def active_provider() -> str:
    """Which provider a call would use right now."""
    if settings.ANTHROPIC_API_KEY:
        return "anthropic"
    if settings.GROQ_API_KEY:
        return "groq"
    return "none"


async def _stream_anthropic(system: str, message: str) -> AsyncIterator[str]:
    from anthropic import AsyncAnthropic

    client = AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
    async with client.messages.stream(
        model=settings.ANTHROPIC_MODEL,
        max_tokens=_MAX_TOKENS,
        system=system,
        messages=[{"role": "user", "content": message}],
    ) as stream:
        async for text in stream.text_stream:
            yield text


def _groq_delta(line: str) -> str | None:
    """Text delta from one Groq SSE `data:` line, or None for keepalive/[DONE]."""
    if not line.startswith("data:"):
        return None
    data = line[len("data:") :].strip()
    if not data or data == "[DONE]":
        return None
    try:
        obj = json.loads(data)
    except json.JSONDecodeError:
        return None
    return ((obj.get("choices") or [{}])[0].get("delta") or {}).get("content")


async def _stream_groq(system: str, message: str) -> AsyncIterator[str]:
    payload = {
        "model": settings.GROQ_MODEL,
        "max_tokens": _MAX_TOKENS,
        "stream": True,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": message},
        ],
    }
    headers = {"Authorization": f"Bearer {settings.GROQ_API_KEY}"}
    async with (
        httpx.AsyncClient(timeout=60) as client,
        client.stream("POST", _GROQ_URL, json=payload, headers=headers) as r,
    ):
        r.raise_for_status()
        async for line in r.aiter_lines():
            delta = _groq_delta(line)
            if delta:
                yield delta


async def stream_chat(system: str, message: str) -> AsyncIterator[str]:
    """Stream the LLM reply as text chunks — Anthropic primary, Groq fallback.

    Falls back to Groq when Anthropic is unset OR when an Anthropic call **fails**
    (bad key, rate-limit, network) before producing any output — so a broken
    `ANTHROPIC_API_KEY` doesn't take AI down if `GROQ_API_KEY` is set. (If Anthropic
    fails mid-stream after emitting text, we re-raise rather than double-answer.)
    """
    if settings.ANTHROPIC_API_KEY:
        started = False
        try:
            async for text in _stream_anthropic(system, message):
                started = True
                yield text
            return
        except Exception:
            if started or not settings.GROQ_API_KEY:
                raise
            # Anthropic failed before any output → fall through to Groq.

    if settings.GROQ_API_KEY:
        async for text in _stream_groq(system, message):
            yield text
        return

    raise RuntimeError("no LLM provider configured")
