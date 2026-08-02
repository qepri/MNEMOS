"""Proves the foundational fixtures (T005-T017) wire together correctly:
a real migrated database, a real document+chunk insert, and the
update_chunk_search_vector DB trigger populating search_vector on commit.
"""
from tests.factories import make_chunk, make_document


def test_migrated_schema_has_a_head_revision(migrated_schema):
    assert migrated_schema


def test_document_and_chunk_round_trip(db_session):
    doc = make_document(db_session)
    chunk = make_chunk(db_session, doc, content="Hello world.")

    from app.models.chunk import Chunk

    fetched = db_session.get(Chunk, chunk.id)
    assert fetched is not None
    assert fetched.document_id == doc.id
    assert fetched.content == "Hello world."
    assert len(fetched.embedding) == 1024


def test_search_vector_trigger_populates_on_commit(committing_db):
    committing_db.info["truncate"] = {"chunks", "documents"}
    doc = make_document(committing_db)
    chunk = make_chunk(committing_db, doc, content="pgvector full text search trigger test")
    committing_db.commit()

    from app.models.chunk import Chunk

    fetched = committing_db.get(Chunk, chunk.id)
    assert fetched.search_vector is not None
