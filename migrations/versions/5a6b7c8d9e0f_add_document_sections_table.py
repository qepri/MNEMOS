"""add document_sections table

Revision ID: 5a6b7c8d9e0f
Revises: 4f9g0h1i2j3k
Create Date: 2026-01-22 17:30:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from pgvector.sqlalchemy import Vector

# revision identifiers, used by Alembic.
revision = '5a6b7c8d9e0f'
down_revision = '4f9g0h1i2j3k'
branch_labels = None
depends_on = None

def upgrade():
    # Create document_sections table
    op.create_table('document_sections',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('document_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=True),
        sa.Column('content', sa.Text(), nullable=True),
        sa.Column('start_page', sa.Integer(), nullable=True),
        sa.Column('end_page', sa.Integer(), nullable=True),
        sa.Column('embedding', Vector(1024), nullable=True), # 1024 dim from settings
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['document_id'], ['documents.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Add HNSW Index
    # Note: We use postgresql_ops to specify the operator class for the vector index
    op.create_index('ix_document_sections_embedding', 'document_sections', ['embedding'], unique=False, postgresql_using='hnsw', postgresql_with={'m': 16, 'ef_construction': 64}, postgresql_ops={'embedding': 'vector_cosine_ops'})


def downgrade():
    op.drop_index('ix_document_sections_embedding', table_name='document_sections', postgresql_using='hnsw')
    op.drop_table('document_sections')
