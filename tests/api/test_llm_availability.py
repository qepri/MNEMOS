"""Contract tests for GET /api/settings/llm-availability (feature 006).

Covers the table in specs/006-llm-optional-mode/contracts/api-llm-availability.md.

`config.settings` is imported inside fixtures/tests rather than at module scope -
see tests/conftest.py: settings bind at import time, so importing early would
pin the dev database URL instead of the test container's.
"""
import pytest

pytestmark = pytest.mark.api


@pytest.fixture(autouse=True)
def clear_availability_cache():
    from app.services.llm_availability import invalidate

    invalidate()
    yield
    invalidate()


@pytest.fixture(autouse=True)
def no_stored_prefs(db_session):
    """Remove any stored UserPreferences row for the duration of these tests.

    LLMClient._resolve_provider ranks the DB above settings.py, so a row left
    committed by another test (stage_summarize creates one as a side effect)
    would silently win over the provider these tests monkeypatch onto settings -
    and they'd pass alone but fail in a full run. Deleted inside the test's
    transaction, which conftest rolls back.
    """
    from app.models.user_preferences import UserPreferences

    db_session.query(UserPreferences).delete()
    db_session.flush()


@pytest.fixture
def local_provider(monkeypatch):
    """Slim-mode default: a local OpenAI-compatible endpoint that may be down."""
    from config.settings import LLMProvider, settings

    monkeypatch.setattr(settings, "LLM_PROVIDER", LLMProvider.LM_STUDIO)
    monkeypatch.setattr(settings, "LOCAL_LLM_BASE_URL", "http://127.0.0.1:59999/v1")


def test_unconfigured_when_hosted_provider_has_no_key(client, monkeypatch):
    from config.settings import LLMProvider, settings

    monkeypatch.setattr(settings, "LLM_PROVIDER", LLMProvider.OPENAI)
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "")

    response = client.get('/api/settings/llm-availability')

    assert response.status_code == 200
    assert response.get_json()["state"] == "unconfigured"


def test_available_when_hosted_provider_has_a_key(client, monkeypatch):
    from config.settings import LLMProvider, settings

    monkeypatch.setattr(settings, "LLM_PROVIDER", LLMProvider.OPENAI)
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "sk-a-real-looking-key")

    body = client.get('/api/settings/llm-availability').get_json()

    assert body["state"] == "available"
    assert body["detail"] is None


def test_unreachable_when_local_endpoint_refuses(client, local_provider):
    """Port 59999 on localhost has nothing listening - the connection is
    refused, which is exactly the slim-mode-without-Ollama case.
    """
    body = client.get('/api/settings/llm-availability').get_json()

    assert body["state"] == "unreachable"
    assert body["detail"]
    assert "59999" in body["endpoint"]


def test_probe_respects_its_timeout(client, local_provider, monkeypatch):
    """Without an explicit timeout the SDK default is 600s. Assert we pass one."""
    import requests

    captured = {}
    real_get = requests.get

    def spy(url, **kwargs):
        captured.update(kwargs)
        return real_get(url, **kwargs)

    monkeypatch.setattr(requests, "get", spy)
    client.get('/api/settings/llm-availability')

    assert captured.get("timeout") is not None
    assert captured["timeout"] <= 10


def test_never_leaks_an_api_key(client, monkeypatch):
    from config.settings import LLMProvider, settings

    secret = "sk-this-must-never-appear-in-a-response"
    monkeypatch.setattr(settings, "LLM_PROVIDER", LLMProvider.OPENAI)
    monkeypatch.setattr(settings, "OPENAI_API_KEY", secret)

    raw = client.get('/api/settings/llm-availability').get_data(as_text=True)

    assert secret not in raw


def test_result_is_cached_within_ttl(client, local_provider, monkeypatch):
    import app.services.llm_availability as availability

    calls = []
    real_check = availability._check
    monkeypatch.setattr(availability, "_check",
                        lambda: (calls.append(1), real_check())[1])

    client.get('/api/settings/llm-availability')
    client.get('/api/settings/llm-availability')
    client.get('/api/settings/llm-availability')

    assert len(calls) == 1


def test_reset_client_invalidates_the_cache(client, local_provider, monkeypatch):
    """Settings changes call reset_client(); availability must re-probe rather
    than serve a stale answer for up to the TTL.
    """
    import app.services.llm_availability as availability
    from app.services.llm_client import reset_client

    calls = []
    real_check = availability._check
    monkeypatch.setattr(availability, "_check",
                        lambda: (calls.append(1), real_check())[1])

    client.get('/api/settings/llm-availability')
    reset_client()
    client.get('/api/settings/llm-availability')

    assert len(calls) == 2


def test_endpoint_returns_200_even_when_the_check_explodes(client, monkeypatch):
    """Availability must never 500 - MNEMOS is up regardless of the LLM."""
    import app.services.llm_availability as availability

    def boom():
        raise RuntimeError("something unexpected")

    monkeypatch.setattr(availability, "_check", boom)

    response = client.get('/api/settings/llm-availability')

    assert response.status_code == 200
    assert response.get_json()["state"] == "unconfigured"
