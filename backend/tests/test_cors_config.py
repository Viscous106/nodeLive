"""CORS origin resolution — regression for the production socket.io 403.

In prod the SPA is served same-origin, so the browser's WebSocket handshake
carries `Origin: https://<service>.onrender.com`. socket.io enforces
`cors_allowed_origins` on that Origin; if the prod URL isn't allowed the
handshake is rejected with 403 and every live-meeting feature dies. Render
injects `RENDER_EXTERNAL_URL`, so `cors_origins` must include it.
"""

from app.core.config import Settings


def test_cors_origins_includes_render_external_url(monkeypatch):
    monkeypatch.setenv("RENDER_EXTERNAL_URL", "https://nodelive.onrender.com")
    s = Settings()
    assert "https://nodelive.onrender.com" in s.cors_origins


def test_cors_origins_absent_render_url(monkeypatch):
    monkeypatch.delenv("RENDER_EXTERNAL_URL", raising=False)
    s = Settings()
    assert all("onrender.com" not in o for o in s.cors_origins)


def test_cors_origins_no_duplicate_when_already_listed(monkeypatch):
    monkeypatch.setenv("CORS_ORIGIN", "https://nodelive.onrender.com")
    monkeypatch.setenv("RENDER_EXTERNAL_URL", "https://nodelive.onrender.com")
    s = Settings()
    assert s.cors_origins.count("https://nodelive.onrender.com") == 1
