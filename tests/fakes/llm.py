"""HTTP-boundary fakes for LLM providers.

Both the OpenAI SDK and the Anthropic SDK send requests over httpx, so a
single respx router faking each provider's chat-completions endpoint lets
LLMClient run for real (provider dispatch, PROVIDER_SPECS, the
unknown-provider -> llamacpp fallback, response parsing) while nothing ever
reaches a live network (research.md D5).
"""
import json

import pytest
import respx
from httpx import Response

_OPENAI_STYLE_ROUTES = {
    "openai": "https://api.openai.com/v1/chat/completions",
    "groq": "https://api.groq.com/openai/v1/chat/completions",
    "cerebras": "https://api.cerebras.ai/v1/chat/completions",
    "deepseek": "https://api.deepseek.com/v1/chat/completions",
}

_ANTHROPIC_ROUTE = "https://api.anthropic.com/v1/messages"


def _openai_completion_payload(text: str) -> dict:
    return {
        "id": "chatcmpl-fake",
        "object": "chat.completion",
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": text},
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
    }


def _anthropic_completion_payload(text: str) -> dict:
    return {
        "id": "msg-fake",
        "type": "message",
        "role": "assistant",
        "content": [{"type": "text", "text": text}],
        "model": "claude-fake",
        "stop_reason": "end_turn",
        "usage": {"input_tokens": 1, "output_tokens": 1},
    }


class FakeLLM:
    """Queues canned responses per provider and records requests sent."""

    def __init__(self, router: respx.MockRouter):
        self._router = router
        self.calls = []

    def completion(self, text: str, provider: str = "openai", base_url: str | None = None):
        """Queue the next response a provider's chat endpoint should return."""
        if provider == "anthropic":
            url = base_url or _ANTHROPIC_ROUTE
            payload = _anthropic_completion_payload(text)
        else:
            url = base_url or _OPENAI_STYLE_ROUTES.get(provider, _OPENAI_STYLE_ROUTES["openai"])
            payload = _openai_completion_payload(text)

        def _responder(request):
            self.calls.append(request)
            return Response(200, json=payload)

        self._router.post(url).mock(side_effect=_responder)

    def llamacpp(self, text: str, base_url: str):
        """llamacpp/lm_studio/custom all speak the OpenAI-compatible schema
        against a locally-configured base_url rather than a fixed provider
        domain.
        """
        self.completion(text=text, provider="llamacpp", base_url=base_url.rstrip("/") + "/chat/completions")


@pytest.fixture
def fake_llm():
    with respx.mock(assert_all_called=False) as router:
        yield FakeLLM(router)
