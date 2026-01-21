"""add_graph_data_to_messages

Revision ID: 4f9g0h1i2j3k
Revises: 3e8f9a2b5c7d
Create Date: 2026-01-20 17:15:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '4f9g0h1i2j3k'
down_revision = '3e8f9a2b5c7d'
branch_labels = None
depends_on = None

def upgrade():
    # Add graph_data column to messages table
    # Using JSONB for efficient storage and potential querying of graph structure
    op.add_column('messages', sa.Column('graph_data', postgresql.JSONB(astext_type=sa.Text()), nullable=True))


def downgrade():
    op.drop_column('messages', 'graph_data')
