"""/api/health (liveness-only) vs /api/ready (liveness + migrations + llama.cpp)
per CLAUDE.md's Health section: /api/ready can be 503 while /api/health stays
200 — e.g. a cold-starting llama.cpp is a normal transient state.

Both routes cache their result for 5s in a closure-local dict, so each test
here advances a fake monotonic clock to force a fresh check rather than
risking a stale cached result from a previous test sharing the same
session-scoped app instance.
"""
import itertools

import pytest

pytestmark = pytest.mark.api

# Module-level (not per-test) so the fake clock only ever advances - a
# per-test counter that resets to 0 could land close enough to a previous
# test's cached timestamp to produce a false cache hit across tests.
_clock = itertools.count()


@pytest.fixture(autouse=True)
def fresh_health_cache(monkeypatch):
    """Force every call in these tests past the 5s cache window."""

    def fake_monotonic():
        return next(_clock) * 10.0

    monkeypatch.setattr("app.time.monotonic", fake_monotonic)


def test_health_is_liveness_only(client):
    resp = client.get("/api/health")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["status"] == "ok"
    assert body["db"] is True
    assert body["redis"] is True


def test_ready_is_503_when_llamacpp_unreachable(client, monkeypatch):
    monkeypatch.setattr(
        "app._llamacpp_status", lambda: {"ok": False, "detail": "connection refused"}
    )
    monkeypatch.setattr("app._migration_status", lambda: {"ok": True})

    resp = client.get("/api/ready")

    assert resp.status_code == 503
    body = resp.get_json()
    assert body["status"] == "not_ready"
    assert body["llamacpp"]["ok"] is False


def test_ready_is_200_when_everything_healthy(client, monkeypatch):
    monkeypatch.setattr("app._llamacpp_status", lambda: {"ok": True})
    monkeypatch.setattr("app._migration_status", lambda: {"ok": True})

    resp = client.get("/api/ready")

    assert resp.status_code == 200
    assert resp.get_json()["status"] == "ready"


def test_health_stays_200_while_ready_is_503(client, monkeypatch):
    """The exact divergence CLAUDE.md documents: llama.cpp cold-starting
    does not mean the app is down.
    """
    monkeypatch.setattr(
        "app._llamacpp_status", lambda: {"ok": False, "detail": "cold start"}
    )
    monkeypatch.setattr("app._migration_status", lambda: {"ok": True})

    assert client.get("/api/health").status_code == 200
    assert client.get("/api/ready").status_code == 503
