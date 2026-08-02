"""Service tests for app/services/rag.py against real Postgres/pgvector:
vector search, keyword search via plainto_tsquery, RRF merge, adjacent-chunk
expansion, and the documented no-document_ids -> no-sources behavior
(CLAUDE.md RAG Query Pipeline section). Only the LLM/embedding HTTP calls
are faked.
"""
import pytest

from tests.factories import make_chunk, make_document

pytestmark = pytest.mark.service


@pytest.fixture(autouse=True)
def openai_provider(monkeypatch):
    from config.settings import settings, LLMProvider
    from app.services.llm_client import reset_client

    monkeypatch.setattr(settings, "LLM_PROVIDER", LLMProvider.OPENAI)
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "test-key")
    reset_client()
    yield
    reset_client()


def test_search_similar_chunks_finds_relevant_chunk_and_its_neighbor(db_session, fake_embeddings):
    from app.services.rag import RAGService

    fake_embeddings.install()
    doc = make_document(db_session, language="english")
    make_chunk(db_session, doc, content="pgvector stores embeddings efficiently.", chunk_index=0)
    target = make_chunk(db_session, doc, content="Reciprocal rank fusion merges vector and keyword search.", chunk_index=1)
    make_chunk(db_session, doc, content="Neighbor chunk that should be pulled in by adjacency expansion.", chunk_index=2)
    db_session.commit()

    rag = RAGService(db_session)
    results = rag.search_similar_chunks("reciprocal rank fusion", document_ids=[str(doc.id)], top_k=5)

    result_indices = {c.chunk_index for c in results}
    assert target.chunk_index in result_indices
    # Adjacent-chunk expansion (chunk_index +/-1) should have pulled in a neighbor.
    assert (target.chunk_index - 1 in result_indices) or (target.chunk_index + 1 in result_indices)


def test_search_similar_chunks_only_returns_chunks_from_requested_documents(db_session, fake_embeddings):
    from app.services.rag import RAGService

    fake_embeddings.install()
    doc_a = make_document(db_session, filename="a.pdf")
    make_chunk(db_session, doc_a, content="Content belonging to document A.", chunk_index=0)
    doc_b = make_document(db_session, filename="b.pdf")
    make_chunk(db_session, doc_b, content="Content belonging to document B.", chunk_index=0)
    db_session.commit()

    rag = RAGService(db_session)
    results = rag.search_similar_chunks("content", document_ids=[str(doc_a.id)], top_k=10)

    assert all(c.document_id == doc_a.id for c in results)


def test_query_without_document_ids_returns_no_sources(db_session, fake_llm, fake_embeddings):
    from app.services.rag import RAGService

    fake_embeddings.install()
    fake_llm.completion(text="A vanilla answer with no document context.", provider="openai")

    rag = RAGService(db_session)
    result = rag.query(question="What is the capital of France?", document_ids=[])

    assert result["sources"] == []
    assert result["answer"]


def test_query_with_document_ids_cites_sources(db_session, fake_llm, fake_embeddings):
    from app.services.rag import RAGService

    fake_embeddings.install()
    doc = make_document(db_session, filename="paris.pdf", original_filename="paris.pdf")
    make_chunk(db_session, doc, content="Paris is the capital of France.", chunk_index=0)
    db_session.commit()

    fake_llm.completion(text="Paris is the capital [Source: paris.pdf].", provider="openai")

    rag = RAGService(db_session)
    result = rag.query(question="What is the capital of France?", document_ids=[str(doc.id)])

    assert result["sources"]
    assert any(doc.filename in str(s) for s in result["sources"])
