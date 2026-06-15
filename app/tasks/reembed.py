"""Re-embed all chunks and concepts with the current EMBEDDING_MODEL.

Used after a user migrates to better hardware and picks a new preset. The
extracted text, summaries, and hypergraph topology are preserved — only
the vector columns get rewritten.
"""
from app.extensions import celery_app, db
from app.models.document import Document
from app.models.chunk import Chunk
from app.models.knowledge_graph import Concept
from app.services.embedder import EmbedderService
from config.settings import settings
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
import logging

logger = logging.getLogger(__name__)

CHUNK_BATCH = 1000
CONCEPT_BATCH = 500


def _current_vector_dim(table: str) -> int | None:
    """Inspect pgvector column to learn its current dimension. None if unknown."""
    try:
        row = db.session.execute(text(
            "SELECT atttypmod FROM pg_attribute "
            "WHERE attrelid = :t::regclass AND attname = 'embedding'"
        ), {"t": table}).first()
        # pgvector stores dim in atttypmod directly
        if row and row[0] and row[0] > 0:
            return int(row[0])
    except SQLAlchemyError:
        db.session.rollback()
    return None


def _resize_vector_column(table: str, new_dim: int):
    """ALTER pgvector column to a new dimension. Existing values get wiped."""
    logger.warning(f"Resizing {table}.embedding to vector({new_dim}). Existing vectors will be cleared.")
    # Drop dependent index first (HNSW indexes are dimension-bound)
    if table == "chunks":
        db.session.execute(text("DROP INDEX IF EXISTS ix_chunks_embedding"))
    db.session.execute(text(f"ALTER TABLE {table} ALTER COLUMN embedding TYPE vector({new_dim}) USING NULL"))
    db.session.commit()


def _recreate_chunk_hnsw_index():
    db.session.execute(text(
        "CREATE INDEX IF NOT EXISTS ix_chunks_embedding ON chunks "
        "USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64)"
    ))
    db.session.commit()


@celery_app.task(bind=True, soft_time_limit=10800, time_limit=14400)
def reembed_all(self):
    """Re-embed every chunk and concept with settings.EMBEDDING_MODEL."""
    from app import create_app
    app = create_app()
    with app.app_context():
        # Force a fresh embedder so a model swap mid-session is picked up
        EmbedderService._model = None
        EmbedderService._client = None

        target_dim = settings.EMBEDDING_DIMENSION
        target_model = settings.EMBEDDING_MODEL
        logger.info(f"Re-embed starting. Target: {target_model} ({target_dim}d)")

        # 1. Resize columns if dimension changed
        for table in ("chunks", "concepts"):
            current = _current_vector_dim(table)
            if current and current != target_dim:
                _resize_vector_column(table, target_dim)

        embedder = EmbedderService()
        total_chunks = db.session.query(Chunk).count()
        total_concepts = db.session.query(Concept).count()
        logger.info(f"Will re-embed {total_chunks} chunks and {total_concepts} concepts")

        # 2. Re-embed chunks in batches, ordered for stable resume
        done = 0
        last_id = None
        while True:
            q = db.session.query(Chunk).order_by(Chunk.id)
            if last_id is not None:
                q = q.filter(Chunk.id > last_id)
            batch = q.limit(CHUNK_BATCH).all()
            if not batch:
                break
            texts = [c.content for c in batch]
            vectors = embedder.embed(texts)
            for chunk, vec in zip(batch, vectors):
                chunk.embedding = vec
            db.session.commit()
            done += len(batch)
            last_id = batch[-1].id
            logger.info(f"Chunks: {done}/{total_chunks}")
            self.update_state(state="PROGRESS", meta={
                "stage": "chunks", "done": done, "total": total_chunks
            })

        # 3. Re-embed concepts
        done = 0
        last_id = None
        while True:
            q = db.session.query(Concept).order_by(Concept.id)
            if last_id is not None:
                q = q.filter(Concept.id > last_id)
            batch = q.limit(CONCEPT_BATCH).all()
            if not batch:
                break
            texts = [(c.name + " " + (c.description or "")).strip() for c in batch]
            vectors = embedder.embed(texts)
            for concept, vec in zip(batch, vectors):
                concept.embedding = vec
            db.session.commit()
            done += len(batch)
            last_id = batch[-1].id
            logger.info(f"Concepts: {done}/{total_concepts}")
            self.update_state(state="PROGRESS", meta={
                "stage": "concepts", "done": done, "total": total_concepts
            })

        # 4. Recreate HNSW index (was dropped if we resized)
        _recreate_chunk_hnsw_index()

        # 5. Stamp documents with the new model
        db.session.execute(text(
            "UPDATE documents SET embedding_model_used = :m"
        ), {"m": target_model})
        db.session.commit()

        logger.info("Re-embed complete.")
        return {
            "chunks": total_chunks,
            "concepts": total_concepts,
            "model": target_model,
            "dimension": target_dim,
        }


# ponytail: in-process smoke check, run with `python -m app.tasks.reembed`
if __name__ == "__main__":
    from app import create_app
    app = create_app()
    with app.app_context():
        # Round-trip: embed a sentence, cosine-search back, confirm match.
        e = EmbedderService()
        v = e.embed("the quick brown fox jumps over the lazy dog")
        assert isinstance(v, list) and len(v) == settings.EMBEDDING_DIMENSION, \
            f"embed returned {type(v).__name__} of len {len(v) if hasattr(v, '__len__') else '?'}, expected list len {settings.EMBEDDING_DIMENSION}"
        # Column-dim probe
        for tbl in ("chunks", "concepts"):
            dim = _current_vector_dim(tbl)
            assert dim == settings.EMBEDDING_DIMENSION, \
                f"{tbl}.embedding is vector({dim}), settings says {settings.EMBEDDING_DIMENSION}. Run reembed_all to align."
        print("OK: embedder + column dims match settings.")
