"""Backfill of LLM-dependent data for already-indexed documents (feature 006, US3).

The point of these tests is FR-009 and FR-014: backfill must never re-extract or
re-embed, and changing providers must never destroy what was already generated.
"""
import pytest

from tests.factories import make_chunk, make_document

pytestmark = pytest.mark.api


def test_status_counts_documents_missing_summaries(client, db_session):
    make_document(db_session, status='completed', summary=None)
    make_document(db_session, status='completed', summary="Already has one.")
    db_session.commit()

    body = client.get('/api/documents/llm-backfill').get_json()

    assert body['needs_summary'] >= 1


def test_status_ignores_documents_that_never_finished_indexing(client, db_session):
    """A document still processing (or errored on extraction) is not a backfill
    candidate - it needs reprocessing, which is a different action.
    """
    make_document(db_session, status='processing', summary=None)
    db_session.commit()

    before = client.get('/api/documents/llm-backfill').get_json()

    make_document(db_session, status='error', summary=None)
    db_session.commit()

    after = client.get('/api/documents/llm-backfill').get_json()

    assert after['needs_summary'] == before['needs_summary']


def test_backfill_enqueues_existing_tasks_without_reprocessing(client, db_session, monkeypatch):
    """FR-009: backfill must reuse the per-document summary/hypergraph tasks and
    must never touch process_document_task, which would re-extract and re-embed.
    """
    from app.tasks import processing

    summary_calls, hypergraph_calls, reprocess_calls = [], [], []

    monkeypatch.setattr(processing.generate_summary_task, 'delay',
                        lambda doc_id: summary_calls.append(doc_id))
    monkeypatch.setattr(processing.reprocess_hypergraph_task, 'delay',
                        lambda doc_id: hypergraph_calls.append(doc_id))
    monkeypatch.setattr(processing.process_document_task, 'delay',
                        lambda *a, **kw: reprocess_calls.append(a))

    doc = make_document(db_session, status='completed', summary=None)
    make_chunk(db_session, doc, content="already embedded", chunk_index=0)
    db_session.commit()

    response = client.post('/api/documents/llm-backfill')

    assert response.status_code == 202
    assert str(doc.id) in summary_calls
    assert reprocess_calls == []


def test_backfill_preserves_existing_summaries(client, db_session, monkeypatch):
    """FR-014: a document that already has a summary is left alone - backfill
    tops up what is missing, it does not regenerate the library.
    """
    from app.tasks import processing

    summary_calls = []
    monkeypatch.setattr(processing.generate_summary_task, 'delay',
                        lambda doc_id: summary_calls.append(doc_id))
    monkeypatch.setattr(processing.reprocess_hypergraph_task, 'delay',
                        lambda doc_id: None)

    kept = make_document(db_session, status='completed', summary="Hand-written summary.")
    db_session.commit()

    client.post('/api/documents/llm-backfill')

    assert str(kept.id) not in summary_calls
    db_session.refresh(kept)
    assert kept.summary == "Hand-written summary."
