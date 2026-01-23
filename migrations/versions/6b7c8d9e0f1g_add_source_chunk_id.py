"""add_source_chunk_id_to_hyper_edges

Revision ID: 6b7c8d9e0f1g
Revises: 5a6b7c8d9e0f
Create Date: 2026-01-22 23:30:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '6b7c8d9e0f1g'
down_revision = '5a6b7c8d9e0f'
branch_labels = None
depends_on = None

def upgrade():
    # Use Inspector to check if column exists
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = [c['name'] for c in inspector.get_columns('hyper_edges')]

    if 'source_chunk_id' not in columns:
        op.add_column('hyper_edges', sa.Column('source_chunk_id', postgresql.UUID(as_uuid=True), nullable=True))
        # Add FK. Name constraints explicitly to avoid auto-gen issues in some DBs
        op.create_foreign_key('fk_hyper_edges_source_chunk_id', 'hyper_edges', 'chunks', ['source_chunk_id'], ['id'])


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = [c['name'] for c in inspector.get_columns('hyper_edges')]
    
    if 'source_chunk_id' in columns:
        op.drop_constraint('fk_hyper_edges_source_chunk_id', 'hyper_edges', type_='foreignkey')
        op.drop_column('hyper_edges', 'source_chunk_id')
