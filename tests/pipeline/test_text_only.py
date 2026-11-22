"""Text-only ingestion: verbatim sources (laws, regulations, contracts) that no LLM may summarize or rewrite.

A document uploaded with `text_only=true` is extracted, chunked and embedded like any other, but the summary and
concept stages are skipped and it is never a backfill candidate. Uses `committing_db` like test_pipeline_no_llm.py,
because process_document_task opens its own app and DB connection.
"""
import pytest

from tests.factories import make_chunk, make_document

pytestmark = pytest.mark.pipeline


@pytest.fixture(autouse=True)
def cleanup_tables(committing_db):
    committing_db.info["truncate"] = {"chunks", "documents", "user_preferences"}
    yield


def test_text_only_document_completes_without_llm_stages(committing_db):
    from app.tasks.processing import process_document_task

    doc = make_document(committing_db, file_type="text", status="pending", metadata_={"text_only": True})
    make_chunk(committing_db, doc, content="Artículo 1. Texto literal.", chunk_index=0)
    committing_db.commit()

    process_document_task.apply(args=[str(doc.id)])

    committing_db.refresh(doc)
    assert doc.status == "completed"
    assert doc.summary is None
    pipeline = doc.metadata_["pipeline"]
    assert pipeline["summarize"] == {**pipeline["summarize"], "status": "skipped", "reason": "text_only"}
    assert pipeline["hypergraph"] == {**pipeline["hypergraph"], "status": "skipped", "reason": "text_only"}


def test_standalone_summary_task_refuses_text_only(committing_db):
    from app.tasks.processing import generate_summary_task

    doc = make_document(committing_db, status="completed", summary=None, metadata_={"text_only": True})
    committing_db.commit()

    result = generate_summary_task.apply(args=[str(doc.id)]).get()

    committing_db.refresh(doc)
    assert result == "Skipped: text_only"
    assert doc.summary is None


@pytest.mark.api
def test_backfill_never_counts_text_only(client, db_session):
    before = client.get('/api/documents/llm-backfill').get_json()

    make_document(db_session, status='completed', summary=None, metadata_={"text_only": True})
    db_session.commit()

    after = client.get('/api/documents/llm-backfill').get_json()
    assert after['needs_summary'] == before['needs_summary']
    assert after['needs_concepts'] == before['needs_concepts']
