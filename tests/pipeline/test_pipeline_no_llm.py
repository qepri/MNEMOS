"""Ingestion must survive with no LLM reachable (feature 006, FR-001/FR-002).

These tests need no special "unreachable LLM" plumbing: conftest's autouse
`no_external_network` guard already raises on any non-localhost connect, which
is exactly the condition a slim deployment with no Ollama running is in. Not
requesting the `fake_llm` fixture *is* the test setup.

Like test_processing.py these use `committing_db` — process_document_task opens
its own Flask app and DB connection, so rows must be really committed to be
visible to it.
"""
import pytest

from tests.factories import make_chunk, make_document

pytestmark = pytest.mark.pipeline


@pytest.fixture(autouse=True)
def cleanup_tables(committing_db):
    committing_db.info["truncate"] = {"chunks", "documents", "user_preferences"}
    yield


def test_document_completes_when_llm_unreachable(committing_db):
    """The headline claim: no LLM must not fail the document.

    Uses the resume path (chunks already present) so the test exercises the
    LLM-dependent stages without needing a real PDF on disk. Extraction and
    embedding are LLM-free by construction - they never build an LLM client.
    """
    from app.tasks.processing import process_document_task

    doc = make_document(committing_db, file_type="pdf", status="pending")
    make_chunk(committing_db, doc, content="indexed without an llm", chunk_index=0)
    committing_db.commit()

    process_document_task.apply(args=[str(doc.id)])

    committing_db.refresh(doc)
    assert doc.status == "completed"
    assert doc.error_message is None
    assert doc.processing_progress == 100


def test_chunks_survive_when_llm_unreachable(committing_db):
    """Embeddings are committed before any LLM stage runs (pipeline.py:282),
    so an absent LLM must never cost the user their index.
    """
    from app.models.chunk import Chunk
    from app.tasks.processing import process_document_task

    doc = make_document(committing_db, file_type="pdf", status="pending")
    make_chunk(committing_db, doc, content="chunk one", chunk_index=0)
    make_chunk(committing_db, doc, content="chunk two", chunk_index=1)
    committing_db.commit()

    process_document_task.apply(args=[str(doc.id)])

    surviving = committing_db.query(Chunk).filter_by(document_id=doc.id).all()
    assert len(surviving) == 2
    assert all(c.embedding is not None for c in surviving)


def test_summarize_records_failure_when_llm_unreachable(committing_db):
    """The stage record must be truthful.

    Before the FR-002 fix this asserted-on value was hardcoded 'completed'
    (pipeline.py:297 recorded success unconditionally because
    _generate_summary_logic swallowed the exception without reporting it), so a
    failed summary was indistinguishable from a real one. Every downstream
    decision - the dormant summary panel, backfill eligibility - reads this.
    """
    from app.tasks.processing import process_document_task

    doc = make_document(committing_db, file_type="pdf", status="pending")
    make_chunk(committing_db, doc, content="some content", chunk_index=0)
    committing_db.commit()

    process_document_task.apply(args=[str(doc.id)])

    committing_db.refresh(doc)
    summarize = doc.metadata_["pipeline"]["summarize"]
    assert summarize["status"] == "failed"
    assert summarize.get("error")


def test_hypergraph_records_failure_when_llm_unreachable(committing_db):
    """stage_hypergraph was already non-blocking; this pins that it stays so."""
    from app.tasks.processing import process_document_task

    doc = make_document(committing_db, file_type="pdf", status="pending")
    make_chunk(committing_db, doc, content="some content", chunk_index=0)
    committing_db.commit()

    process_document_task.apply(args=[str(doc.id)])

    committing_db.refresh(doc)
    assert doc.metadata_["pipeline"]["hypergraph"]["status"] == "failed"


def test_summary_stays_empty_rather_than_partial(committing_db):
    """A failed summary must leave the column NULL, not a truncated artifact -
    the SPA uses null-summary + failed-stage to decide what to offer the user.
    """
    from app.tasks.processing import process_document_task

    doc = make_document(committing_db, file_type="pdf", status="pending")
    make_chunk(committing_db, doc, content="some content", chunk_index=0)
    committing_db.commit()

    process_document_task.apply(args=[str(doc.id)])

    committing_db.refresh(doc)
    assert not doc.summary
