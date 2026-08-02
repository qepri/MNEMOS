"""API tests for /api/chat: no-document_ids answers from the model's own
knowledge with no sources (documented as intended, not a bug, in
CLAUDE.md's RAG Query Pipeline section), using fake_llm so no real network
call is made.
"""
import pytest

pytestmark = pytest.mark.api


@pytest.fixture(autouse=True)
def openai_provider(monkeypatch):
    from config.settings import settings, LLMProvider
    from app.services.llm_client import reset_client

    monkeypatch.setattr(settings, "LLM_PROVIDER", LLMProvider.OPENAI)
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "test-key")
    reset_client()
    yield
    reset_client()


def test_chat_without_document_ids_returns_answer_and_no_sources(client, db_session, fake_llm, fake_embeddings):
    # The route creates a UserPreferences row with defaults if none exists,
    # and UserPreferences.llm_provider defaults to 'lm_studio' at the DB
    # level - which would then outrank settings.LLM_PROVIDER per the
    # constructor-arg > DB > settings priority. Seed it explicitly so the
    # route resolves to the provider this test actually fakes.
    from app.models.user_preferences import UserPreferences

    db_session.add(UserPreferences(llm_provider="openai", openai_api_key="test-key"))
    db_session.commit()

    fake_embeddings.install()
    fake_llm.completion(text="The sky is blue due to Rayleigh scattering.", provider="openai")

    resp = client.post("/api/chat/", json={"question": "Why is the sky blue?"})

    assert resp.status_code == 200
    body = resp.get_json()
    assert body["answer"]
    assert body["sources"] == []
    assert "conversation_id" in body


def test_chat_requires_a_question(client):
    resp = client.post("/api/chat/", json={"question": ""})
    assert resp.status_code == 400
