"""Smoke tests — the app boots and the liveness probe answers.

These run without a database (the `/health` probe has no dependencies) so they
stay green in any environment. Readiness (`/health/ready`) is exercised in CI
where Postgres is available.
"""

import os

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_app_imports_and_creates():
    assert app.title == "nodeLive"


def test_health_liveness():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_health_readiness_when_db_available():
    """Only assert readiness when a database is wired (CI / local docker)."""
    if not os.environ.get("DATABASE_URL"):
        return
    resp = client.get("/health/ready")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ready"
