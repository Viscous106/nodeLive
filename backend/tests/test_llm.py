"""LLM provider wrapper: Groq SSE parsing, provider selection, and dispatch
(Anthropic primary, Groq fallback). The live HTTP calls need real keys; these
test the pure logic + the selection seam."""

import pytest

import app.utils.llm as llm


def test_groq_delta_extracts_content():
    line = 'data: {"choices":[{"delta":{"content":"Hello"}}]}'
    assert llm._groq_delta(line) == "Hello"


def test_groq_delta_ignores_done_keepalive_and_empty():
    assert llm._groq_delta("data: [DONE]") is None
    assert llm._groq_delta("") is None
    assert llm._groq_delta(": keepalive") is None  # comment line, not data:
    assert llm._groq_delta('data: {"choices":[{"delta":{}}]}') is None  # no content
    assert llm._groq_delta("data: not json") is None


def test_is_configured_and_active_provider(monkeypatch):
    monkeypatch.setattr(llm.settings, "ANTHROPIC_API_KEY", "")
    monkeypatch.setattr(llm.settings, "GROQ_API_KEY", "")
    assert llm.is_configured() is False
    assert llm.active_provider() == "none"

    monkeypatch.setattr(llm.settings, "GROQ_API_KEY", "gk")
    assert llm.is_configured() is True
    assert llm.active_provider() == "groq"

    monkeypatch.setattr(llm.settings, "ANTHROPIC_API_KEY", "ak")
    assert llm.active_provider() == "anthropic"  # Anthropic wins when both set


async def test_stream_chat_uses_groq_when_only_groq(monkeypatch):
    monkeypatch.setattr(llm.settings, "ANTHROPIC_API_KEY", "")
    monkeypatch.setattr(llm.settings, "GROQ_API_KEY", "gk")

    async def fake_groq(system, message):
        yield "a"
        yield "b"

    monkeypatch.setattr(llm, "_stream_groq", fake_groq)
    out = [c async for c in llm.stream_chat("sys", "msg")]
    assert out == ["a", "b"]


async def test_stream_chat_prefers_anthropic(monkeypatch):
    monkeypatch.setattr(llm.settings, "ANTHROPIC_API_KEY", "ak")
    monkeypatch.setattr(llm.settings, "GROQ_API_KEY", "gk")

    async def fake_anth(system, message):
        yield "x"

    async def fake_groq(system, message):
        yield "GROQ"  # must NOT appear

    monkeypatch.setattr(llm, "_stream_anthropic", fake_anth)
    monkeypatch.setattr(llm, "_stream_groq", fake_groq)
    out = [c async for c in llm.stream_chat("sys", "msg")]
    assert out == ["x"]


async def test_stream_chat_raises_when_unconfigured(monkeypatch):
    monkeypatch.setattr(llm.settings, "ANTHROPIC_API_KEY", "")
    monkeypatch.setattr(llm.settings, "GROQ_API_KEY", "")
    with pytest.raises(RuntimeError):
        _ = [c async for c in llm.stream_chat("sys", "msg")]


async def test_stream_chat_falls_back_to_groq_when_anthropic_fails(monkeypatch):
    # Anthropic key set but the call fails before any output → use Groq.
    monkeypatch.setattr(llm.settings, "ANTHROPIC_API_KEY", "bad-key")
    monkeypatch.setattr(llm.settings, "GROQ_API_KEY", "gk")

    async def boom_anth(system, message):
        raise RuntimeError("401 invalid api key")
        yield  # pragma: no cover  (makes this an async generator)

    async def fake_groq(system, message):
        yield "from-groq"

    monkeypatch.setattr(llm, "_stream_anthropic", boom_anth)
    monkeypatch.setattr(llm, "_stream_groq", fake_groq)
    out = [c async for c in llm.stream_chat("sys", "msg")]
    assert out == ["from-groq"]


async def test_stream_chat_reraises_if_anthropic_fails_mid_stream(monkeypatch):
    # If Anthropic already emitted text then fails, don't double-answer with Groq.
    monkeypatch.setattr(llm.settings, "ANTHROPIC_API_KEY", "ak")
    monkeypatch.setattr(llm.settings, "GROQ_API_KEY", "gk")

    async def partial_then_fail(system, message):
        yield "partial"
        raise RuntimeError("dropped mid-stream")

    monkeypatch.setattr(llm, "_stream_anthropic", partial_then_fail)
    with pytest.raises(RuntimeError):
        _ = [c async for c in llm.stream_chat("sys", "msg")]
