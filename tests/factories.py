"""Builders for Document/Chunk rows used across the suite.

Mirrors the real models rather than substituting for them (data-model.md
DocumentFixture/ChunkFixture) — no mocking of the DB or ORM (FR-003).
"""
from tests.fakes.embeddings import deterministic_vector


def make_document(session, **overrides):
    from app.models.document import Document

    defaults = dict(
        filename="test.pdf",
        original_filename="test.pdf",
        file_type="pdf",
        status="completed",
        language="english",
        metadata_={},
    )
    defaults.update(overrides)

    doc = Document(**defaults)
    session.add(doc)
    session.flush()
    return doc


def make_chunk(session, document, **overrides):
    from app.models.chunk import Chunk

    content = overrides.pop("content", "Some chunk content.")
    defaults = dict(
        document_id=document.id,
        content=content,
        chunk_index=0,
        language=document.language or "english",
        embedding=deterministic_vector(content),
        metadata_={},
    )
    # search_vector is intentionally never set here — it is the DB
    # trigger's job (update_chunk_search_vector). Setting it manually would
    # mask trigger breakage.
    defaults.update(overrides)

    chunk = Chunk(**defaults)
    session.add(chunk)
    session.flush()
    return chunk
