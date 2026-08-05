"""Retrieval must be entirely LLM-free (feature 006, FR-005 / SC-003).

The premise of LLM-optional mode is that search is untouched by whether a
language model exists. These tests deliberately do NOT install `fake_llm`, so
conftest's `no_external_network` guard makes any attempted LLM call an error -
which is what a slim deployment with no Ollama running actually looks like.

Note `lm_studio` rather than the `openai` provider used in test_rag.py: it is
the slim-mode default and the one that points at a local endpoint that may not
exist.
"""
import pytest

from tests.factories import make_chunk, make_document

pytestmark = pytest.mark.service


@pytest.fixture(autouse=True)
def slim_provider(monkeypatch):
    from config.settings import settings, LLMProvider
    from app.services.llm_client import reset_client

    monkeypatch.setattr(settings, "LLM_PROVIDER", LLMProvider.LM_STUDIO)
    reset_client()
    yield
    reset_client()


def _library(session):
    doc = make_document(session, language="english")
    make_chunk(session, doc, content="pgvector stores embeddings efficiently.", chunk_index=0)
    make_chunk(session, doc, content="Reciprocal rank fusion merges vector and keyword search.", chunk_index=1)
    make_chunk(session, doc, content="Maximal marginal relevance reduces redundancy in results.", chunk_index=2)
    session.commit()
    return doc


def test_rag_service_constructs_without_a_reachable_llm(db_session):
    """RAGService builds its client eagerly in __init__. For an OpenAI-compatible
    provider that is object construction only - no network call - so an absent
    server must not stop a user from searching.
    """
    from app.services.rag import RAGService

    rag = RAGService(db_session)

    assert rag is not None


def test_vector_search_works_without_an_llm(db_session, fake_embeddings):
    from app.services.rag import RAGService

    fake_embeddings.install()
    doc = _library(db_session)

    rag = RAGService(db_session)
    results = rag.search_similar_chunks(
        "reciprocal rank fusion", document_ids=[str(doc.id)], top_k=5
    )

    assert results
    assert any("rank fusion" in c.content.lower() for c in results)


def test_keyword_search_works_without_an_llm(db_session, fake_embeddings, committing_db):
    """FTS runs off the search_vector trigger - pure Postgres, no LLM."""
    from app.models.chunk import Chunk
    from app.services.rag import RAGService

    fake_embeddings.install()
    committing_db.info["truncate"] = {"chunks", "documents"}
    doc = make_document(committing_db, language="english")
    make_chunk(committing_db, doc, content="Maximal marginal relevance reduces redundancy.", chunk_index=0)
    committing_db.commit()

    rag = RAGService(committing_db)
    results = rag.search_similar_chunks(
        "marginal relevance", document_ids=[str(doc.id)], top_k=5
    )

    assert results


def test_search_results_identical_with_and_without_llm(db_session, fake_embeddings, fake_llm):
    """SC-003: the retrieval stack must be provably untouched by this feature.

    Runs the same query twice against the same corpus - once with an LLM faked
    as reachable, once without - and asserts the retrieved chunk set is
    identical. If a future change makes retrieval consult the LLM, this fails.
    """
    from app.services.rag import RAGService

    fake_embeddings.install()
    doc = _library(db_session)
    query = "reciprocal rank fusion"

    without_llm = RAGService(db_session).search_similar_chunks(
        query, document_ids=[str(doc.id)], top_k=5
    )

    fake_llm.llamacpp("irrelevant", base_url="http://host.docker.internal:1234/v1")
    with_llm = RAGService(db_session).search_similar_chunks(
        query, document_ids=[str(doc.id)], top_k=5
    )

    assert [c.id for c in without_llm] == [c.id for c in with_llm]
