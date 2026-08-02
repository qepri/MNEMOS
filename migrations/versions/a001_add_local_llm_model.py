"""add user_preferences.local_llm_model

The model declared this column and code accessed it via
`getattr(prefs, 'local_llm_model', None)` because the column had never been
created. This revision creates it so the workaround can be removed.

Additive and nullable: no backfill, no risk to existing rows.

Revision ID: a001_local_llm_model
Revises: 594d02684e1e
Create Date: 2026-08-02

"""
from alembic import op
import sqlalchemy as sa

revision = 'a001_local_llm_model'
down_revision = '594d02684e1e'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        'user_preferences',
        sa.Column('local_llm_model', sa.String(length=255), nullable=True),
    )


def downgrade():
    op.drop_column('user_preferences', 'local_llm_model')
