"""migrate stored ollama provider references to llamacpp

Ollama was replaced by llama.cpp. Stored preference rows may still name it;
one live row had memory_provider='ollama'. All three statements are written
even though only one matched at authoring time, so the revision is correct
against any database state (including an older restored backup).

Runtime already tolerates a stale value - LLMClient falls back to llamacpp on
an unrecognised provider - so this revision is a cleanup, not a hard
prerequisite for the app to boot.

Revision ID: a003_ollama_fallback
Revises: a002_coll_backfill
Create Date: 2026-08-02

"""
from alembic import op

revision = 'a003_ollama_fallback'
down_revision = 'a002_coll_backfill'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("UPDATE user_preferences SET memory_provider = 'llamacpp' WHERE memory_provider = 'ollama'")
    op.execute("UPDATE user_preferences SET llm_provider = 'llamacpp' WHERE llm_provider = 'ollama'")
    op.execute("UPDATE llm_connections SET provider_type = 'custom' WHERE provider_type = 'ollama'")


def downgrade():
    # Not reversible: the original per-row value is not recoverable once
    # overwritten, and restoring 'ollama' would point at a backend that no
    # longer exists. A documented no-op beats a fake inverse.
    pass
