"""add images to messages

Revision ID: d4e5f6g7h8i9
Revises: c3f6e9bef27c
Create Date: 2026-01-07 10:10:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'd4e5f6g7h8i9'
down_revision = 'c3f6e9bef27c'
branch_labels = None
depends_on = None


def upgrade():
    # Add images column to messages table
    op.add_column('messages', sa.Column('images', postgresql.JSONB(astext_type=sa.Text()), nullable=True))


def downgrade():
    # Remove images column
    op.drop_column('messages', 'images')
