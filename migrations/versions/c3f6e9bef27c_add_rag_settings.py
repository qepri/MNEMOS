"""add_rag_settings

Revision ID: c3f6e9bef27c
Revises: 
Create Date: 2025-12-21 00:34:03.889867

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c3f6e9bef27c'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # Import UUID type
    from sqlalchemy.dialects.postgresql import UUID
    import uuid

    # Get database connection
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    # Get list of existing tables
    existing_tables = inspector.get_table_names()

    # Create system_prompts table if it doesn't exist
    if 'system_prompts' not in existing_tables:
        op.create_table('system_prompts',
            sa.Column('id', UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
            sa.Column('title', sa.String(length=255), nullable=False),
            sa.Column('content', sa.Text(), nullable=False),
            sa.Column('is_default', sa.Boolean(), nullable=False, server_default='false'),
            sa.Column('is_editable', sa.Boolean(), nullable=False, server_default='true'),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.Column('updated_at', sa.DateTime(), nullable=True)
        )

    # Create llm_connections table if it doesn't exist (needed for FK)
    if 'llm_connections' not in existing_tables:
        op.create_table('llm_connections',
            sa.Column('id', UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
            sa.Column('name', sa.String(length=255), nullable=False),
            sa.Column('provider', sa.String(length=50), nullable=False),
            sa.Column('base_url', sa.String(length=255), nullable=True),
            sa.Column('api_key', sa.String(length=255), nullable=True),
            sa.Column('model_name', sa.String(length=255), nullable=True),
            sa.Column('is_active', sa.Boolean(), nullable=False, server_default='false'),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.Column('updated_at', sa.DateTime(), nullable=True)
        )

    # Create user_preferences table if it doesn't exist
    if 'user_preferences' not in existing_tables:
        op.create_table('user_preferences',
            sa.Column('id', UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
            sa.Column('use_conversation_context', sa.Boolean(), nullable=False, server_default='true'),
            sa.Column('max_context_messages', sa.Integer(), nullable=False, server_default='10'),
            sa.Column('selected_system_prompt_id', UUID(as_uuid=True), nullable=True),
            sa.Column('active_connection_id', UUID(as_uuid=True), nullable=True),
            sa.Column('chunk_size', sa.Integer(), nullable=False, server_default='512'),
            sa.Column('chunk_overlap', sa.Integer(), nullable=False, server_default='50'),
            sa.Column('selected_llm_model', sa.String(length=255), nullable=True),
            sa.Column('whisper_model', sa.String(length=50), nullable=False, server_default='base'),
            sa.Column('llm_provider', sa.String(length=50), nullable=False, server_default='lm_studio'),
            sa.Column('openai_api_key', sa.String(length=255), nullable=True),
            sa.Column('anthropic_api_key', sa.String(length=255), nullable=True),
            sa.Column('groq_api_key', sa.String(length=255), nullable=True),
            sa.Column('custom_api_key', sa.String(length=255), nullable=True),
            sa.Column('transcription_provider', sa.String(length=50), nullable=False, server_default='local'),
            sa.Column('local_llm_base_url', sa.String(length=255), nullable=True, server_default='http://host.docker.internal:1234/v1'),
            sa.Column('memory_enabled', sa.Boolean(), nullable=False, server_default='false'),
            sa.Column('memory_provider', sa.String(length=50), nullable=False, server_default='ollama'),
            sa.Column('memory_llm_model', sa.String(length=255), nullable=True),
            sa.Column('max_memories', sa.Integer(), nullable=False, server_default='50'),
            sa.Column('ollama_num_ctx', sa.Integer(), nullable=False, server_default='2048'),
            sa.Column('web_search_provider', sa.String(length=50), nullable=False, server_default='duckduckgo'),
            sa.Column('tavily_api_key', sa.String(length=255), nullable=True),
            sa.Column('brave_search_api_key', sa.String(length=255), nullable=True),
            sa.Column('deepgram_api_key', sa.String(length=255), nullable=True),
            sa.Column('tts_provider', sa.String(length=50), nullable=False, server_default='browser'),
            sa.Column('stt_provider', sa.String(length=50), nullable=False, server_default='browser'),
            sa.Column('tts_voice', sa.String(length=255), nullable=True),
            sa.Column('tts_enabled', sa.Boolean(), nullable=False, server_default='false'),
            sa.Column('openai_tts_model', sa.String(length=50), nullable=True, server_default='tts-1'),
            sa.Column('openai_stt_model', sa.String(length=50), nullable=True, server_default='whisper-1'),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.Column('updated_at', sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(['selected_system_prompt_id'], ['system_prompts.id'], ),
            sa.ForeignKeyConstraint(['active_connection_id'], ['llm_connections.id'], )
        )
    else:
        # Table exists, only add missing columns
        columns = [c['name'] for c in inspector.get_columns('user_preferences')]
        with op.batch_alter_table('user_preferences', schema=None) as batch_op:
            if 'chunk_size' not in columns:
                batch_op.add_column(sa.Column('chunk_size', sa.Integer(), nullable=False, server_default='512'))
            if 'chunk_overlap' not in columns:
                batch_op.add_column(sa.Column('chunk_overlap', sa.Integer(), nullable=False, server_default='50'))
            if 'selected_llm_model' not in columns:
                batch_op.add_column(sa.Column('selected_llm_model', sa.String(length=255), nullable=True))

    # Create conversations table if it doesn't exist
    if 'conversations' not in existing_tables:
        op.create_table('conversations',
            sa.Column('id', UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
            sa.Column('title', sa.String(length=255), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.Column('updated_at', sa.DateTime(), nullable=True)
        )

    # Create messages table if it doesn't exist
    if 'messages' not in existing_tables:
        op.create_table('messages',
            sa.Column('id', UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
            sa.Column('conversation_id', UUID(as_uuid=True), nullable=False),
            sa.Column('role', sa.String(length=50), nullable=False),
            sa.Column('content', sa.Text(), nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(['conversation_id'], ['conversations.id'], ondelete='CASCADE')
        )

    # Create collections table if it doesn't exist
    if 'collections' not in existing_tables:
        op.create_table('collections',
            sa.Column('id', UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
            sa.Column('name', sa.String(length=255), nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=True)
        )

    # Create documents table if it doesn't exist
    if 'documents' not in existing_tables:
        op.create_table('documents',
            sa.Column('id', UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
            sa.Column('collection_id', UUID(as_uuid=True), nullable=True),
            sa.Column('filename', sa.String(length=255), nullable=False),
            sa.Column('file_path', sa.String(length=512), nullable=False),
            sa.Column('file_type', sa.String(length=50), nullable=True),
            sa.Column('upload_date', sa.DateTime(), nullable=True),
            sa.Column('processing_status', sa.String(length=50), nullable=True, server_default='pending'),
            sa.Column('task_id', sa.String(length=255), nullable=True),
            sa.ForeignKeyConstraint(['collection_id'], ['collections.id'], ondelete='SET NULL')
        )

    # Create chunks table if it doesn't exist
    if 'chunks' not in existing_tables:
        op.create_table('chunks',
            sa.Column('id', UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
            sa.Column('document_id', UUID(as_uuid=True), nullable=False),
            sa.Column('content', sa.Text(), nullable=False),
            sa.Column('embedding', sa.LargeBinary(), nullable=True),
            sa.Column('chunk_index', sa.Integer(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(['document_id'], ['documents.id'], ondelete='CASCADE')
        )

    # Create user_memories table if it doesn't exist
    if 'user_memories' not in existing_tables:
        op.create_table('user_memories',
            sa.Column('id', UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
            sa.Column('memory_text', sa.Text(), nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.Column('last_accessed_at', sa.DateTime(), nullable=True)
        )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    # Drop tables in reverse order (respecting foreign key constraints)
    op.drop_table('user_memories')
    op.drop_table('chunks')
    op.drop_table('documents')
    op.drop_table('collections')
    op.drop_table('messages')
    op.drop_table('conversations')
    op.drop_table('user_preferences')
    op.drop_table('llm_connections')
    op.drop_table('system_prompts')
    # ### end Alembic commands ###
