"""Pipeline stage tests: each stage in app/tasks/pipeline.py called directly
against a real database, asserting Document.metadata_['pipeline'] records
each stage's outcome (CLAUDE.md Document Processing Pipeline section).
"""
import pytest

from tests.factories import make_document

pytestmark = pytest.mark.pipeline


def test_stage_extract_routes_by_file_type_and_records_progress(db_session, monkeypatch):
    from app.tasks import pipeline

    stub_chunks = [{"text": "a page of text", "page": 1, "chunk_index": 0}]
    monkeypatch.setitem(pipeline.EXTRACTORS, "pdf", lambda doc: stub_chunks)

    doc = make_document(db_session, file_type="pdf")
    db_session.commit()

    result = pipeline.stage_extract(doc)

    assert result == stub_chunks
    assert doc.metadata_["pipeline"]["extract"]["status"] == "completed"
    assert doc.processing_progress == 30


def test_stage_detect_language_english(db_session):
    from app.tasks import pipeline

    doc = make_document(db_session)
    db_session.commit()
    text_chunks = [{"text": "The quick brown fox jumps over the lazy dog."}]

    language = pipeline.stage_detect_language(doc, text_chunks)

    assert language == "english"
    assert doc.language == "english"
    assert doc.metadata_["pipeline"]["detect_language"]["status"] == "completed"


def test_stage_embed_and_save_persists_chunks(db_session, fake_embeddings):
    from app.tasks import pipeline

    fake_embeddings.install()
    doc = make_document(db_session)
    db_session.commit()
    text_chunks = [
        {"text": "first chunk"},
        {"text": "second chunk"},
        {"text": "third chunk"},
    ]

    count = pipeline.stage_embed_and_save(doc, text_chunks, "english")

    assert count == 3
    from app.models.chunk import Chunk

    saved = db_session.query(Chunk).filter_by(document_id=doc.id).order_by(Chunk.chunk_index).all()
    assert [c.content for c in saved] == ["first chunk", "second chunk", "third chunk"]
    assert [c.chunk_index for c in saved] == [0, 1, 2]
    assert doc.processing_progress == 70
    assert doc.metadata_["pipeline"]["embed"]["status"] == "completed"


def test_stage_embed_and_save_skips_when_no_chunks(db_session):
    from app.tasks import pipeline

    doc = make_document(db_session)
    db_session.commit()

    count = pipeline.stage_embed_and_save(doc, [], "english")

    assert count == 0
    assert doc.metadata_["pipeline"]["embed"]["status"] == "skipped"


def test_stage_summarize_calls_summary_fn_and_records_completion(db_session):
    from app.tasks import pipeline

    doc = make_document(db_session, metadata_={})
    db_session.commit()
    calls = []

    def fake_summary(doc_id):
        # A real summary_fn writes the summary onto the document; the stage
        # checks for that rather than trusting the absence of an exception,
        # because SummaryService swallows per-batch LLM failures internally.
        calls.append(doc_id)
        doc.summary = "A generated summary."

    pipeline.stage_summarize(doc, fake_summary)

    assert calls == [doc.id]
    assert doc.metadata_["pipeline"]["summarize"]["status"] == "completed"


def test_stage_summarize_records_failure_when_no_summary_produced(db_session):
    """SummaryService can return normally having produced nothing - every LLM
    call inside it may have failed and been logged. That must not be recorded
    as a success, or the UI cannot tell it from a real summary.
    """
    from app.tasks import pipeline

    doc = make_document(db_session, metadata_={})
    db_session.commit()

    pipeline.stage_summarize(doc, lambda doc_id: None)

    summarize = doc.metadata_["pipeline"]["summarize"]
    assert summarize["status"] == "failed"
    assert "no summary produced" in summarize["error"]


def test_stage_summarize_records_failure_when_summary_fn_raises(db_session):
    from app.tasks import pipeline

    doc = make_document(db_session, metadata_={})
    db_session.commit()

    def boom(doc_id):
        raise RuntimeError("Connection refused")

    pipeline.stage_summarize(doc, boom)

    summarize = doc.metadata_["pipeline"]["summarize"]
    assert summarize["status"] == "failed"
    assert "Connection refused" in summarize["error"]


def test_stage_summarize_skips_when_summary_already_present(db_session):
    from app.tasks import pipeline

    doc = make_document(db_session, summary="Already summarized.")
    db_session.commit()
    calls = []

    pipeline.stage_summarize(doc, lambda doc_id: calls.append(doc_id))

    assert calls == []
    assert doc.metadata_["pipeline"]["summarize"]["status"] == "skipped"


def test_save_transcription_failure_is_non_blocking(db_session, monkeypatch, tmp_path):
    from app.tasks import pipeline
    from config.settings import settings

    monkeypatch.setattr(settings, "TRANSCRIPTION_FOLDER", str(tmp_path))
    monkeypatch.setattr(
        pipeline.TranscriptionService, "save_to_txt",
        staticmethod(lambda segments, path: (_ for _ in ()).throw(OSError("disk full"))),
    )

    doc = make_document(db_session, metadata_={})
    db_session.commit()

    pipeline._save_transcription(doc, [{"start": 0.0, "text": "hi"}], "transcript.txt")  # must not raise

    assert "transcription_file" not in (doc.metadata_ or {})


def test_stage_hypergraph_failure_is_non_blocking(db_session, monkeypatch):
    from app.tasks import pipeline
    from app.services.hypergraph_extractor import HypergraphExtractor

    def _boom(doc_id):
        raise RuntimeError("LLM provider unavailable")

    monkeypatch.setattr(HypergraphExtractor, "process_document", staticmethod(_boom))

    doc = make_document(db_session)
    db_session.commit()

    pipeline.stage_hypergraph(doc)  # must not raise

    assert doc.metadata_["pipeline"]["hypergraph"]["status"] == "failed"
    assert "LLM provider unavailable" in doc.metadata_["pipeline"]["hypergraph"]["error"]
