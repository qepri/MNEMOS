"""HTTP-boundary fake for the remote embedding path.

EmbedderService in "local" mode loads a real sentence-transformers model
(multi-GB download, GPU-adjacent) — tests instead configure the remote
OpenAI-compatible embedding provider and fake its HTTP endpoint, so the
real request-building/retry/batching code in EmbedderService still runs,
just without a live network call or a model download (research.md D5).
"""
import hashlib

import pytest
import respx
from httpx import Response

EMBEDDING_DIMENSION = 1024


def deterministic_vector(text: str, dimension: int = EMBEDDING_DIMENSION) -> list[float]:
    """Same text -> same vector, so similarity-search assertions are stable."""
    digest = hashlib.sha256(text.encode("utf-8")).digest()
    # Repeat the digest to cover `dimension` floats, normalize into [-1, 1].
    raw = (digest * (dimension // len(digest) + 1))[:dimension]
    return [(b / 127.5) - 1.0 for b in raw]


class FakeEmbeddings:
    def __init__(self, router: respx.MockRouter):
        self._router = router

    def install(self, base_url: str = "https://api.openai.com/v1", dimension: int = EMBEDDING_DIMENSION):
        url = base_url.rstrip("/") + "/embeddings"

        def _responder(request):
            import json as _json

            body = _json.loads(request.content)
            inputs = body["input"] if isinstance(body["input"], list) else [body["input"]]
            data = [
                {"index": i, "embedding": deterministic_vector(text, dimension), "object": "embedding"}
                for i, text in enumerate(inputs)
            ]
            return Response(
                200,
                json={
                    "object": "list",
                    "data": data,
                    "model": "fake-embedding-model",
                    "usage": {"prompt_tokens": 1, "total_tokens": 1},
                },
            )

        self._router.post(url).mock(side_effect=_responder)


@pytest.fixture
def fake_embeddings(monkeypatch):
    """Also resets EmbedderService's class-level client/model singletons so
    a base_url configured by an earlier test can't leak into this one.
    """
    from app.services.embedder import EmbedderService
    from config.settings import settings

    monkeypatch.setattr(settings, "EMBEDDING_PROVIDER", "openai")
    monkeypatch.setattr(settings, "EMBEDDING_DIMENSION", EMBEDDING_DIMENSION)
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(EmbedderService, "_client", None)
    monkeypatch.setattr(EmbedderService, "_model", None)

    with respx.mock(assert_all_called=False) as router:
        yield FakeEmbeddings(router)
