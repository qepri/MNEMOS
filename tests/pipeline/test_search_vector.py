"""Regression guard for the historical bug where chunks.search_vector was
always NULL (or always indexed as English regardless of the row's actual
language): the update_chunk_search_vector trigger must use the language
stored on the row, and that language must be spelled the same way at
index-time (app/tasks/pipeline.py's PG_LANG_MAP) and query-time
(RAGService._detect_query_language) - both map to full config names like
'english'/'spanish', never raw ISO codes (CLAUDE.md Database section).
"""
import pytest

from tests.factories import make_chunk, make_document

pytestmark = pytest.mark.pipeline


@pytest.fixture(autouse=True)
def cleanup_tables(committing_db):
    committing_db.info["truncate"] = {"chunks", "documents", "user_preferences"}
    yield


def test_trigger_populates_search_vector_for_english(committing_db):
    from app.models.chunk import Chunk
    from sqlalchemy import func

    doc = make_document(committing_db, language="english")
    chunk = make_chunk(committing_db, doc, content="The quick brown fox.", language="english", chunk_index=0)
    committing_db.commit()

    english_hit = committing_db.query(Chunk).filter(
        Chunk.id == chunk.id,
        Chunk.search_vector.op("@@")(func.plainto_tsquery("english", "quick fox")),
    ).first()

    assert english_hit is not None


def test_trigger_populates_search_vector_for_spanish(committing_db):
    from app.models.chunk import Chunk
    from sqlalchemy import func

    doc = make_document(committing_db, language="spanish")
    chunk = make_chunk(committing_db, doc, content="El rápido zorro marrón.", language="spanish", chunk_index=0)
    committing_db.commit()

    spanish_hit = committing_db.query(Chunk).filter(
        Chunk.id == chunk.id,
        Chunk.search_vector.op("@@")(func.plainto_tsquery("spanish", "zorro rápido")),
    ).first()

    assert spanish_hit is not None


def test_index_time_and_query_time_language_maps_agree_on_shared_codes():
    """Both maps must produce the same Postgres config name for any ISO
    code they both handle, or keyword search silently breaks (as it did
    historically) for that language.
    """
    from app.tasks.pipeline import PG_LANG_MAP
    from app.services.rag import RAGService

    query_map = RAGService._PG_LANG_MAP
    shared_codes = set(PG_LANG_MAP) & set(query_map)

    assert shared_codes, "index-time and query-time maps share no codes"
    for code in shared_codes:
        assert PG_LANG_MAP[code] == query_map[code], (
            f"language code {code!r} maps to different configs at "
            f"index-time ({PG_LANG_MAP[code]!r}) vs query-time ({query_map[code]!r})"
        )
