"""add collections and library fields

Revision ID: e5f6g7h8i9j0
Revises: d4e5f6g7h8i9
Create Date: 2026-01-16 14:15:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
# ...
revision = 'e5f6g7h8i9j0'
down_revision = 'addebd1cadcd'
branch_labels = None
depends_on = None


def upgrade():
    # Helper to check existence
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()

    # Create collections table if not exists
    if 'collections' not in tables:
        op.create_table('collections',
            sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column('name', sa.String(length=255), nullable=False),
            sa.Column('description', sa.Text(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.Column('updated_at', sa.DateTime(), nullable=True),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('name')
        )

    # Add columns to documents table
    existing_columns = [c['name'] for c in inspector.get_columns('documents')]
    
    if 'collection_id' not in existing_columns:
        op.add_column('documents', sa.Column('collection_id', postgresql.UUID(as_uuid=True), nullable=True))
        # Add foreign key constraint only if column was added (safe assumption for this specific fix)
        op.create_foreign_key(None, 'documents', 'collections', ['collection_id'], ['id'])
        
    if 'tag' not in existing_columns:
        op.add_column('documents', sa.Column('tag', sa.String(length=255), nullable=True))
    
    if 'stars' not in existing_columns:
        op.add_column('documents', sa.Column('stars', sa.Integer(), nullable=True, server_default='0'))
        
    if 'comment' not in existing_columns:
        op.add_column('documents', sa.Column('comment', sa.Text(), nullable=True))



def downgrade():
    # Drop foreign key constraint
    op.drop_constraint(None, 'documents', type_='foreignkey')

    # Drop columns from documents table
    op.drop_column('documents', 'comment')
    op.drop_column('documents', 'stars')
    op.drop_column('documents', 'tag')
    op.drop_column('documents', 'collection_id')

    # Drop collections table
    op.drop_table('collections')
