"""Is an LLM usable right now?

MNEMOS indexes and searches without a language model (feature 006), so the UI
needs to know which features to offer rather than assuming a model is there.
Three states, not two - see FR-006: telling someone to install Ollama when
Ollama is installed but not running is a wrong instruction.

Deliberately NOT keyed on settings.LLM_PROVIDER alone. Slim deployments ship
LLM_PROVIDER=lm_studio pointing at host.docker.internal whether or not anything
listens there, so "a provider is configured" is not "a model is reachable".
(/api/ready's llama.cpp probe *is* keyed on the setting, on purpose - readiness
reflects deploy-time infrastructure and must not flap when a user toggles a
runtime preference. This answers a different question.)
"""
import logging
import time

import requests

from config.settings import LLMProvider, settings

logger = logging.getLogger(__name__)

UNCONFIGURED = "unconfigured"
UNREACHABLE = "unreachable"
AVAILABLE = "available"

# Short enough that starting Ollama shows up without a page reload, long enough
# that rendering a document list doesn't fan out into one probe per row.
CACHE_TTL_SECONDS = 30

# Mandatory, not a tuning knob: no LLM client in this codebase passes timeout=,
# so the inherited SDK default is 600s. A probe that can block for ten minutes
# is not a probe.
PROBE_TIMEOUT_SECONDS = 2.0

# Providers whose endpoint we do not own. Spending a live request on every page
# load to prove api.openai.com is up would be rude and slow; a usable key is
# enough to say the feature is on.
_HOSTED_PROVIDERS = {
    LLMProvider.OPENAI,
    LLMProvider.ANTHROPIC,
    LLMProvider.GROQ,
    LLMProvider.CEREBRAS,
    LLMProvider.DEEPSEEK,
}

# Placeholders the codebase hands to local servers that ignore auth. Treating
# these as real credentials would report a hosted provider as configured when
# the user has entered nothing.
_PLACEHOLDER_KEYS = {"not-needed", "lm-studio", "custom", "gsk_...", ""}

_cache = {"result": None, "at": 0.0}


def invalidate():
    """Drop the cached result. Called from reset_client() so a settings change
    takes effect immediately rather than up to CACHE_TTL_SECONDS later.
    """
    _cache["result"] = None
    _cache["at"] = 0.0


def _result(state, provider=None, endpoint=None, detail=None):
    return {
        "state": state,
        "provider": provider,
        "endpoint": endpoint,
        "detail": detail,
        "checked_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }


def _has_real_key(client) -> bool:
    key = getattr(client, "api_key", None)
    return bool(key) and str(key).strip().lower() not in _PLACEHOLDER_KEYS


def _probe(base_url: str) -> tuple[bool, str | None]:
    """GET {base_url}/models - the OpenAI-compatible listing endpoint, which
    Ollama, LM Studio, vLLM and llama-server all serve.
    """
    url = f"{str(base_url).rstrip('/')}/models"
    try:
        response = requests.get(url, timeout=PROBE_TIMEOUT_SECONDS)
    except requests.RequestException as e:
        return False, f"{type(e).__name__} contacting {base_url}"
    if response.status_code >= 500:
        return False, f"Server returned {response.status_code} at {base_url}"
    return True, None


def _check() -> dict:
    """Resolve the configured provider and decide which of the three states holds."""
    try:
        from app.services.llm_client import LLMClient
        client = LLMClient()
    except Exception as e:
        # The CUSTOM provider raises outright when no connection row is
        # selected. That is a configuration gap, not an outage.
        return _result(UNCONFIGURED, detail=str(e))

    provider = client.provider
    provider_name = getattr(provider, "value", str(provider))

    if provider in _HOSTED_PROVIDERS:
        if _has_real_key(client.client):
            return _result(AVAILABLE, provider=provider_name)
        return _result(
            UNCONFIGURED,
            provider=provider_name,
            detail=f"No API key configured for {provider_name}.",
        )

    # Local, self-hosted: llamacpp / lm_studio / custom-with-connection.
    # Never return the key - the endpoint is safe to show, credentials are not.
    endpoint = str(getattr(client.client, "base_url", "") or "")
    if not endpoint:
        return _result(UNCONFIGURED, provider=provider_name,
                       detail="No LLM endpoint configured.")

    ok, detail = _probe(endpoint)
    if ok:
        return _result(AVAILABLE, provider=provider_name, endpoint=endpoint)
    return _result(UNREACHABLE, provider=provider_name, endpoint=endpoint, detail=detail)


def get_availability(force: bool = False) -> dict:
    """Cached three-state availability. Never raises - a probe failure is a
    state, not an error, because MNEMOS itself is up either way.
    """
    now = time.time()
    if not force and _cache["result"] and (now - _cache["at"]) < CACHE_TTL_SECONDS:
        return _cache["result"]

    try:
        result = _check()
    except Exception as e:  # noqa: BLE001 - availability must never 500
        logger.warning(f"LLM availability check failed unexpectedly: {e}")
        result = _result(UNCONFIGURED, detail=str(e))

    _cache["result"] = result
    _cache["at"] = now
    return result
