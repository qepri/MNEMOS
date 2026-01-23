"""fix_hyperedge_chunk_fk_cascade

Revision ID: 7c8d9e0f1g2h
Revises: 6b7c8d9e0f1g
Create Date: 2026-01-22 23:45:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '7c8d9e0f1g2h'
down_revision = '6b7c8d9e0f1g'
branch_labels = None
depends_on = None

def upgrade():
    # Drop existing FK (name might depend on auto-naming if not explicit, but we named it explicitly in previous migration)
    # constraint name used in previous migration: 'fk_hyper_edges_source_chunk_id'
    
    op.drop_constraint('fk_hyper_edges_source_chunk_id', 'hyper_edges', type_='foreignkey')
    
    # Re-create with CASCADE
    op.create_foreign_key(
        'fk_hyper_edges_source_chunk_id', 
        'hyper_edges', 
        'chunks', 
        ['source_chunk_id'], 
        ['id'],
        ondelete='CASCADE'
    )

def downgrade():
    op.drop_constraint('fk_hyper_edges_source_chunk_id', 'hyper_edges', type_='foreignkey')
    
    # Re-create without CASCADE (legacy state)
    op.create_foreign_key(
        'fk_hyper_edges_source_chunk_id', 
        'hyper_edges', 
        'chunks', 
        ['source_chunk_id'], 
        ['id']
    )
