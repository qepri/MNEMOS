"""allow 'text' in file_type_enum, for plain-text documents

The extractor for plain text lands in the same change that adds this revision,
but the enum is what actually gates it: without 'text' as a valid value the
upload fails at INSERT with a DataError, after the file has already been
written to disk.

Additive and safe on a live database: no existing row changes, and every
current value stays valid.

downgrade() is deliberately a no-op with an explanation rather than a lie.
Postgres cannot remove a value from an enum in place; undoing this properly
means recreating the type, which would require rewriting every documents row
and would fail outright if any document already uses 'text'. Reverting the code
is enough — an unused enum value costs nothing.

Revision ID: a007_file_type_text
Revises: a006_fix_ts_config
Create Date: 2026-08-29

"""
from alembic import op

revision = 'a007_file_type_text'
down_revision = 'a006_fix_ts_config'
branch_labels = None
depends_on = None


def upgrade():
    # ADD VALUE cannot run inside a transaction block on older servers, and
    # Alembic wraps migrations in one. autocommit_block() steps outside it.
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE file_type_enum ADD VALUE IF NOT EXISTS 'text'")


def downgrade():
    # Intentionally does nothing. See the module docstring: removing an enum
    # value in Postgres means recreating the type, which is destructive and
    # impossible if any row already uses it. Leaving it costs nothing.
    pass
