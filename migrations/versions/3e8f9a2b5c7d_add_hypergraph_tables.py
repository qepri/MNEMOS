"""add_hypergraph_tables

Revision ID: 3e8f9a2b5c7d
Revises: f8fe04793e92
Create Date: 2026-01-20 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from pgvector.sqlalchemy import Vector

# revision identifiers, used by Alembic.
revision = '3e8f9a2b5c7d'
down_revision = 'f8fe04793e92'
branch_labels = None
depends_on = None

def upgrade():
    # Use Inspector to check if tables exist (handle potential manual creation or sync issues)
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = inspector.get_table_names()

    # 1. Create Concepts table
    if 'concepts' not in existing_tables:
        op.create_table(
            'concepts',
            sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column('name', sa.String(length=255), nullable=False),
            sa.Column('description', sa.Text(), nullable=True),
            sa.Column('embedding', Vector(768), nullable=True), # Assuming 768 dim
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.PrimaryKeyConstraint('id')
        )
        op.create_index(op.f('ix_concepts_name'), 'concepts', ['name'], unique=True)

    # 2. Create HyperEdges table
    if 'hyper_edges' not in existing_tables:
        op.create_table(
            'hyper_edges',
            sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column('description', sa.Text(), nullable=False),
            sa.Column('embedding', Vector(768), nullable=True),
            sa.Column('source_document_id', postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(['source_document_id'], ['documents.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id')
        )

    # 3. Create HyperEdgeMembers table
    if 'hyper_edge_members' not in existing_tables:
        op.create_table(
            'hyper_edge_members',
            sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column('hyper_edge_id', postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column('concept_id', postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column('role', sa.String(length=50), nullable=True),
            sa.ForeignKeyConstraint(['concept_id'], ['concepts.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['hyper_edge_id'], ['hyper_edges.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id')
        )
        # Indexes for fast Traversal
        op.create_index(op.f('ix_hyper_edge_members_concept_id'), 'hyper_edge_members', ['concept_id'], unique=False)
        op.create_index(op.f('ix_hyper_edge_members_hyper_edge_id'), 'hyper_edge_members', ['hyper_edge_id'], unique=False)


def downgrade():
    op.drop_index(op.f('ix_hyper_edge_members_hyper_edge_id'), table_name='hyper_edge_members')
    op.drop_index(op.f('ix_hyper_edge_members_concept_id'), table_name='hyper_edge_members')
    op.drop_table('hyper_edge_members')
    op.drop_table('hyper_edges')
    op.drop_index(op.f('ix_concepts_name'), table_name='concepts')
    op.drop_table('concepts')
