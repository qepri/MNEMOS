"""backfill collection_documents from the legacy documents.collection_id FK

This INSERT previously ran on every application start inside create_app().
It is idempotent (ON CONFLICT DO NOTHING) and was already applied long ago,
so this is a no-op against the current data. It lives here so the logic is
part of migration history instead of startup.

Revision ID: a002_coll_backfill
Revises: a001_local_llm_model
Create Date: 2026-08-02

"""
from alembic import op

revision = 'a002_coll_backfill'
down_revision = 'a001_local_llm_model'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        INSERT INTO collection_documents (collection_id, document_id)
        SELECT collection_id, id FROM documents
        WHERE collection_id IS NOT NULL
        ON CONFLICT (collection_id, document_id) DO NOTHING
    """)


def downgrade():
    # Deliberately not reversible: the junction rows are indistinguishable
    # from ones created normally through the UI, so removing them would
    # destroy legitimate user data.
    pass
