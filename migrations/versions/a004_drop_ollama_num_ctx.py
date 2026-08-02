"""drop the dead user_preferences.ollama_num_ctx column

*** THE ONLY DESTRUCTIVE SCHEMA OPERATION IN THIS FEATURE ***

Deliberate and reviewed (spec FR-024). Isolated in its own revision so it can
be reverted independently of every additive change around it.

The column held llama.cpp-era-obsolete Ollama tuning state (one live row, the
default 2048). Nothing reads it after the Ollama purge: llama.cpp takes its
context size from LLAMACPP_NUM_CTX in the compose environment.

downgrade() restores the column AND its only value exactly, because the
server_default repopulates every existing row with 2048.

Revision ID: a004_drop_ollama_ctx
Revises: a003_ollama_fallback
Create Date: 2026-08-02

"""
from alembic import op
import sqlalchemy as sa

revision = 'a004_drop_ollama_ctx'
down_revision = 'a003_ollama_fallback'
branch_labels = None
depends_on = None


def upgrade():
    op.drop_column('user_preferences', 'ollama_num_ctx')


def downgrade():
    op.add_column(
        'user_preferences',
        sa.Column(
            'ollama_num_ctx',
            sa.Integer(),
            server_default=sa.text('2048'),
            nullable=False,
        ),
    )
