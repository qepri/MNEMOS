"""Service tests for app/services/embedder.py: remote (OpenAI-compatible)
embedding path, dimension enforcement, and batching. The real HTTP request
code runs; only the network call is faked (research.md D5) so no
sentence-transformers model download is needed in CI.
"""
import pytest

pytestmark = pytest.mark.service


@pytest.fixture(autouse=True)
def openai_api_key(monkeypatch):
    from config.settings import settings

    monkeypatch.setattr(settings, "OPENAI_API_KEY", "test-key")


def test_embed_single_text_returns_correct_dimension(fake_embeddings):
    from app.services.embedder import EmbedderService

    fake_embeddings.install()
    vector = EmbedderService().embed("hello world")

    assert len(vector) == 1024


def test_embed_is_deterministic_for_the_same_text(fake_embeddings):
    from app.services.embedder import EmbedderService

    fake_embeddings.install()
    service = EmbedderService()

    assert service.embed("same text") == service.embed("same text")


def test_embed_batch_of_texts_returns_one_vector_each(fake_embeddings):
    from app.services.embedder import EmbedderService

    fake_embeddings.install()
    vectors = EmbedderService().embed(["a", "b", "c"])

    assert len(vectors) == 3
    assert all(len(v) == 1024 for v in vectors)
