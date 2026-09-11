"""API tests for app/api/settings.py: persisting chat/provider preferences
to UserPreferences via GET/POST /api/settings/chat.
"""
import pytest

pytestmark = pytest.mark.api


def test_get_chat_settings_returns_defaults_when_no_prefs_exist(client):
    resp = client.get("/api/settings/chat")
    assert resp.status_code == 200


def test_post_chat_settings_persists_preferences(client, db_session):
    from app.models.user_preferences import UserPreferences

    # Delete-first makes the unordered .first() below deterministic regardless of
    # test order: other suites commit a real UserPreferences row into the shared
    # container (the singleton table leaks across tests), and the get-or-create
    # endpoint + this assertion both use .first(). See tests/services/test_llm_client.
    db_session.query(UserPreferences).delete()

    resp = client.post(
        "/api/settings/chat",
        json={"chunk_size": 800, "chunk_overlap": 100, "memory_enabled": True},
    )
    assert resp.status_code == 200
    assert resp.get_json()["success"] is True

    prefs = db_session.query(UserPreferences).first()
    assert prefs.chunk_size == 800
    assert prefs.chunk_overlap == 100
    assert prefs.memory_enabled is True


def test_post_chat_settings_clamps_chunk_size_to_configured_bounds(client, db_session):
    from app.models.user_preferences import UserPreferences

    # See note above: clear leaked rows so .first() returns the row this test wrote.
    db_session.query(UserPreferences).delete()

    resp = client.post("/api/settings/chat", json={"chunk_size": 999999})
    assert resp.status_code == 200

    prefs = db_session.query(UserPreferences).first()
    assert prefs.chunk_size <= 2000
