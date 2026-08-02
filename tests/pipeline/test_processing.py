"""Orchestrator + resume-logic tests for app/tasks/processing.py.

process_document_task builds its own Flask app / DB connection internally
(as it does in production, running inside a real Celery worker), so these
tests use `committing_db` rather than the rollback-based `db_session`: rows
must be visible across the connection the task opens for itself, which an
uncommitted transaction on a different connection would not be.
"""
import pytest

from tests.factories import make_chunk, make_document

pytestmark = pytest.mark.pipeline


@pytest.fixture(autouse=True)
def cleanup_tables(committing_db):
    # user_preferences is included because stage_summarize/stage_hypergraph
    # can create a default row as a side effect (mirroring the same
    # get-or-create pattern app/api/chat.py uses) - left uncleaned, it would
    # leak into later tests that rely on UserPreferences.first().
    committing_db.info["truncate"] = {"chunks", "documents", "user_preferences"}
    yield


def test_resume_skips_extraction_when_chunks_already_exist(committing_db):
    from app.tasks.processing import process_document_task

    doc = make_document(committing_db, file_type="pdf", status="pending")
    make_chunk(committing_db, doc, content="pre-existing chunk", chunk_index=0)
    committing_db.commit()

    process_document_task.apply(args=[str(doc.id)])

    committing_db.refresh(doc)
    assert doc.status == "completed"
    assert doc.metadata_["pipeline"]["extract"]["status"] == "skipped"
    assert doc.metadata_["pipeline"]["extract"]["reason"] == "chunks already exist"


def test_missing_document_returns_without_raising(committing_db):
    from app.tasks.processing import process_document_task
    import uuid

    result = process_document_task.apply(args=[str(uuid.uuid4())])

    assert result.get() == "Document not found"
