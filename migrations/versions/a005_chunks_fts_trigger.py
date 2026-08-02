"""repair full-text search on chunks: create the trigger and backfill

CLAIM CORRECTED: CLAUDE.md and the model comment both stated that
chunks.search_vector was "maintained by a DB trigger
(update_chunk_search_vector)". That trigger never existed - the live database
had zero triggers and all 6150 chunks had search_vector IS NULL.

Consequence: RAGService._hybrid_search filters on
`Chunk.search_vector @@ query`, which matched nothing, every time. The
documented hybrid RRF retrieval has silently been running as pure vector
search since inception.

This revision creates the function + trigger and backfills existing rows.

SAFETY (spec HC-2/HC-3): writes ONLY search_vector. It never reads, alters or
invalidates `embedding`, never drops or recreates `chunks`, never re-embeds,
and never touches the vector dimension.

LANGUAGE CONFIG: the mapping below is a deliberate mirror of
RAGService._detect_query_language. Index-time and query-time configurations
must agree or lookups silently return nothing - which is the failure mode
this revision exists to fix. Keep the two in sync.

Revision ID: a005_chunks_fts
Revises: a004_drop_ollama_ctx
Create Date: 2026-08-02

"""
from alembic import op

revision = 'a005_chunks_fts'
down_revision = 'a004_drop_ollama_ctx'
branch_labels = None
depends_on = None


# Mirrors RAGService._detect_query_language (app/services/rag.py).
LANG_EXPR = """
        CASE lower(coalesce(lang, 'en'))
            WHEN 'en' THEN 'english'
            WHEN 'es' THEN 'spanish'
            WHEN 'de' THEN 'german'
            WHEN 'fr' THEN 'french'
            WHEN 'it' THEN 'italian'
            WHEN 'ru' THEN 'russian'
            WHEN 'pt' THEN 'portuguese'
            WHEN 'nl' THEN 'dutch'
            ELSE 'english'
        END
"""


def upgrade():
    op.execute(f"""
        CREATE OR REPLACE FUNCTION chunk_ts_config(lang VARCHAR)
        RETURNS regconfig AS $$
        SELECT ({LANG_EXPR})::regconfig;
        $$ LANGUAGE sql IMMUTABLE;
    """)

    op.execute("""
        CREATE OR REPLACE FUNCTION update_chunk_search_vector()
        RETURNS trigger AS $$
        BEGIN
            NEW.search_vector := to_tsvector(
                chunk_ts_config(NEW.language),
                coalesce(NEW.content, '')
            );
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)

    op.execute("DROP TRIGGER IF EXISTS update_chunk_search_vector ON chunks")
    op.execute("""
        CREATE TRIGGER update_chunk_search_vector
        BEFORE INSERT OR UPDATE OF content, language ON chunks
        FOR EACH ROW EXECUTE FUNCTION update_chunk_search_vector();
    """)

    # Backfill existing rows. Touches search_vector only.
    op.execute("""
        UPDATE chunks
        SET search_vector = to_tsvector(chunk_ts_config(language), coalesce(content, ''))
        WHERE search_vector IS NULL
    """)


def downgrade():
    op.execute("DROP TRIGGER IF EXISTS update_chunk_search_vector ON chunks")
    op.execute("DROP FUNCTION IF EXISTS update_chunk_search_vector()")
    op.execute("DROP FUNCTION IF EXISTS chunk_ts_config(VARCHAR)")
    op.execute("UPDATE chunks SET search_vector = NULL")
