"""fix chunk_ts_config: chunks.language holds config names, not ISO codes

Corrects a005. That revision assumed chunks.language held two-letter
langdetect codes ('en', 'es'), but the pipeline stores full PostgreSQL text
search configuration names: app/tasks/processing.py maps the detected code
through lang_map and persists e.g. 'english', 'spanish', 'russian', falling
back to 'simple'. Its comment even reads "our trigger maps unknown strings to
'simple'" - written against a trigger that had never existed.

Under a005 every value fell through to the ELSE branch, so all rows were
indexed with the english configuration. Verified: all 13 spanish chunks
matched to_tsvector('english', ...) and none matched the spanish equivalent.
The 5916 english chunks were correct only by coincidence.

This revision accepts the stored configuration name directly, still tolerates
ISO codes defensively, and falls back to 'simple' - matching the fallback the
ingestion pipeline already writes. It then re-backfills every row.

Only search_vector is rewritten; embeddings are untouched.

Revision ID: a006_fix_ts_config
Revises: a005_chunks_fts
Create Date: 2026-08-02

"""
from alembic import op

revision = 'a006_fix_ts_config'
down_revision = 'a005_chunks_fts'
branch_labels = None
depends_on = None


# Config names written by app/tasks/processing.py, plus ISO-code tolerance.
# An explicit whitelist keeps the function genuinely IMMUTABLE (no catalog
# lookups) and prevents an invalid regconfig cast from raising inside a
# trigger, which would block ingestion.
LANG_CASE = """
        CASE lower(coalesce(lang, ''))
            WHEN 'english'    THEN 'english'
            WHEN 'spanish'    THEN 'spanish'
            WHEN 'german'     THEN 'german'
            WHEN 'french'     THEN 'french'
            WHEN 'italian'    THEN 'italian'
            WHEN 'russian'    THEN 'russian'
            WHEN 'portuguese' THEN 'portuguese'
            WHEN 'dutch'      THEN 'dutch'
            WHEN 'swedish'    THEN 'swedish'
            WHEN 'norwegian'  THEN 'norwegian'
            WHEN 'danish'     THEN 'danish'
            WHEN 'finnish'    THEN 'finnish'
            WHEN 'en' THEN 'english'
            WHEN 'es' THEN 'spanish'
            WHEN 'de' THEN 'german'
            WHEN 'fr' THEN 'french'
            WHEN 'it' THEN 'italian'
            WHEN 'ru' THEN 'russian'
            WHEN 'pt' THEN 'portuguese'
            WHEN 'nl' THEN 'dutch'
            WHEN 'sv' THEN 'swedish'
            WHEN 'no' THEN 'norwegian'
            WHEN 'da' THEN 'danish'
            WHEN 'fi' THEN 'finnish'
            ELSE 'simple'
        END
"""


def upgrade():
    op.execute(f"""
        CREATE OR REPLACE FUNCTION chunk_ts_config(lang VARCHAR)
        RETURNS regconfig AS $$
        SELECT ({LANG_CASE})::regconfig;
        $$ LANGUAGE sql IMMUTABLE;
    """)

    # Rewrite every row, not just NULLs: a005 populated them all with the
    # wrong configuration.
    op.execute("""
        UPDATE chunks
        SET search_vector = to_tsvector(chunk_ts_config(language), coalesce(content, ''))
    """)


def downgrade():
    # Restore the a005 (incorrect) mapping so the chain is symmetric.
    op.execute("""
        CREATE OR REPLACE FUNCTION chunk_ts_config(lang VARCHAR)
        RETURNS regconfig AS $$
        SELECT (CASE lower(coalesce(lang, 'en'))
            WHEN 'en' THEN 'english'
            WHEN 'es' THEN 'spanish'
            WHEN 'de' THEN 'german'
            WHEN 'fr' THEN 'french'
            WHEN 'it' THEN 'italian'
            WHEN 'ru' THEN 'russian'
            WHEN 'pt' THEN 'portuguese'
            WHEN 'nl' THEN 'dutch'
            ELSE 'english'
        END)::regconfig;
        $$ LANGUAGE sql IMMUTABLE;
    """)
    op.execute("""
        UPDATE chunks
        SET search_vector = to_tsvector(chunk_ts_config(language), coalesce(content, ''))
    """)
