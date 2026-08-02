"""Service tests for app/services/llm_client.py: provider priority
(constructor arg > DB UserPreferences > settings.py), table-driven
PROVIDER_SPECS dispatch, and the unknown-provider -> llamacpp fallback
(CLAUDE.md LLM Client section). Real client construction, fake at the HTTP
transport layer only (FR-003).
"""
import pytest

pytestmark = pytest.mark.service


def test_unknown_stored_provider_falls_back_to_llamacpp(db_session):
    from app.services.llm_client import LLMClient
    from config.settings import LLMProvider

    client = LLMClient(provider="ollama")

    assert client.provider == LLMProvider.LLAMACPP


def test_constructor_arg_takes_priority_over_settings(db_session, monkeypatch):
    from app.services.llm_client import LLMClient
    from config.settings import settings, LLMProvider

    monkeypatch.setattr(settings, "LLM_PROVIDER", LLMProvider.LLAMACPP)

    client = LLMClient(provider=LLMProvider.OPENAI, api_key="sk-test")

    assert client.provider == LLMProvider.OPENAI


def test_db_preference_overrides_settings_default(db_session, monkeypatch):
    from app.services.llm_client import LLMClient
    from app.models.user_preferences import UserPreferences
    from config.settings import settings, LLMProvider

    monkeypatch.setattr(settings, "LLM_PROVIDER", LLMProvider.LLAMACPP)
    # Delete-first makes this deterministic regardless of test order: other
    # suites' get-or-create paths (e.g. app/api/chat.py) may have already
    # committed a real UserPreferences row for real via committing_db.
    db_session.query(UserPreferences).delete()
    db_session.add(UserPreferences(llm_provider=LLMProvider.OPENAI.value, openai_api_key="sk-test"))
    db_session.commit()

    client = LLMClient()

    assert client.provider == LLMProvider.OPENAI


def test_chat_dispatches_to_openai_endpoint_via_provider_specs(db_session, fake_llm, monkeypatch):
    from app.services.llm_client import LLMClient
    from config.settings import settings, LLMProvider

    monkeypatch.setattr(settings, "LLM_PROVIDER", LLMProvider.OPENAI)
    fake_llm.completion(text="fixed reply", provider="openai")

    client = LLMClient(api_key="sk-test")
    reply = client.chat(system="be terse", messages=[{"role": "user", "content": "hi"}])

    assert reply == "fixed reply"
    assert len(fake_llm.calls) == 1
