"""baseline_live_schema

Baseline reflecting the schema as it existed on the live database on
2026-08-01, before Alembic was adopted. The live DB is STAMPED with this
revision, never upgraded into it - upgrade() exists so a fresh database can
be built from scratch.

Reflects verified live state:
  - phase2_strip_embeddings.sql was already applied (the four vector columns
    it drops are absent here by design).
  - The four ad-hoc startup ALTERs were already applied (retrieval_top_k,
    hypergraph_llm_provider, hypergraph_llm_model, embedding_model_used are
    present here).
  - chunks.search_vector exists with its GIN index but NO trigger: the
    documented update_chunk_search_vector trigger never existed, leaving all
    6150 rows NULL. Repaired by a later revision, not assumed here.

Revision ID: 594d02684e1e
Revises: 
Create Date: 2026-08-02 02:03:36.309535

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
import pgvector.sqlalchemy

# revision identifiers, used by Alembic.
revision = '594d02684e1e'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # pgvector must exist before any VECTOR column is created.
    op.execute('CREATE EXTENSION IF NOT EXISTS vector')

    op.create_table('collections',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('name', sa.String(length=255), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('updated_at', sa.DateTime(), nullable=True),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('name')
    )
    op.create_table('concepts',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('name', sa.String(length=255), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('embedding', pgvector.sqlalchemy.vector.VECTOR(dim=1024), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('concepts', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_concepts_name'), ['name'], unique=True)

    op.create_table('conversations',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('title', sa.String(length=255), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('updated_at', sa.DateTime(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('llm_connections',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('name', sa.String(length=255), nullable=False),
    sa.Column('provider_type', sa.String(length=50), nullable=False),
    sa.Column('base_url', sa.String(length=512), nullable=True),
    sa.Column('api_key', sa.String(length=512), nullable=True),
    sa.Column('default_model', sa.String(length=255), nullable=True),
    sa.Column('models', sa.JSON(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('updated_at', sa.DateTime(), nullable=True),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('name')
    )
    op.create_table('system_prompts',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('title', sa.String(length=255), nullable=False),
    sa.Column('content', sa.Text(), nullable=False),
    sa.Column('is_default', sa.Boolean(), nullable=False),
    sa.Column('is_editable', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('updated_at', sa.DateTime(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('user_memories',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('content', sa.String(length=512), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('videomix_projects',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('title', sa.String(length=255), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('user_prompt', sa.Text(), nullable=False),
    sa.Column('document_ids', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('resolution', sa.String(length=20), nullable=True),
    sa.Column('title_cards_enabled', sa.Boolean(), nullable=True),
    sa.Column('max_duration_seconds', sa.Integer(), nullable=True),
    sa.Column('audio_normalization', sa.Boolean(), nullable=True),
    sa.Column('status', sa.Enum('draft', 'generating_script', 'script_ready', 'rendering', 'completed', 'error', name='videomixstatusenum'), nullable=False),
    sa.Column('error_message', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('documents',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('filename', sa.String(length=255), nullable=False),
    sa.Column('original_filename', sa.String(length=255), nullable=True),
    sa.Column('file_type', sa.Enum('pdf', 'audio', 'video', 'youtube', 'epub', name='file_type_enum'), nullable=False),
    sa.Column('file_path', sa.String(length=512), nullable=True),
    sa.Column('youtube_url', sa.String(length=512), nullable=True),
    sa.Column('status', sa.Enum('pending', 'processing', 'completed', 'error', name='status_enum'), nullable=True),
    sa.Column('error_message', sa.Text(), nullable=True),
    sa.Column('processing_progress', sa.Integer(), nullable=True),
    sa.Column('metadata_', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('updated_at', sa.DateTime(), nullable=True),
    sa.Column('collection_id', sa.UUID(), nullable=True),
    sa.Column('tag', sa.String(length=255), nullable=True),
    sa.Column('stars', sa.Integer(), nullable=True),
    sa.Column('comment', sa.Text(), nullable=True),
    sa.Column('language', sa.String(length=50), nullable=True),
    sa.Column('summary', sa.Text(), nullable=True),
    sa.Column('embedding_model_used', sa.String(length=255), nullable=True),
    sa.ForeignKeyConstraint(['collection_id'], ['collections.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('messages',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('conversation_id', sa.UUID(), nullable=False),
    sa.Column('role', sa.String(length=50), nullable=False),
    sa.Column('content', sa.Text(), nullable=False),
    sa.Column('sources', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('search_queries', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('images', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('audio_path', sa.String(length=512), nullable=True),
    sa.Column('graph_data', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.ForeignKeyConstraint(['conversation_id'], ['conversations.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('user_preferences',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('use_conversation_context', sa.Boolean(), nullable=False),
    sa.Column('max_context_messages', sa.Integer(), nullable=False),
    sa.Column('selected_system_prompt_id', sa.UUID(), nullable=True),
    sa.Column('active_connection_id', sa.UUID(), nullable=True),
    sa.Column('chunk_size', sa.Integer(), nullable=False),
    sa.Column('chunk_overlap', sa.Integer(), nullable=False),
    sa.Column('retrieval_top_k', sa.Integer(), nullable=False),
    sa.Column('selected_llm_model', sa.String(length=255), nullable=True),
    sa.Column('whisper_model', sa.String(length=50), nullable=False),
    sa.Column('llm_provider', sa.String(length=50), nullable=False),
    sa.Column('openai_api_key', sa.String(length=255), nullable=True),
    sa.Column('anthropic_api_key', sa.String(length=255), nullable=True),
    sa.Column('groq_api_key', sa.String(length=255), nullable=True),
    sa.Column('custom_api_key', sa.String(length=255), nullable=True),
    sa.Column('transcription_provider', sa.String(length=50), nullable=False),
    sa.Column('local_llm_base_url', sa.String(length=255), nullable=True),
    sa.Column('memory_enabled', sa.Boolean(), nullable=False),
    sa.Column('memory_provider', sa.String(length=50), nullable=False),
    sa.Column('memory_llm_model', sa.String(length=255), nullable=True),
    sa.Column('max_memories', sa.Integer(), nullable=False),
    # Present in the live schema at stamp time; dropped by a later revision
    # as part of the Ollama removal. Declared here so this baseline is a
    # truthful snapshot rather than a post-cleanup state.
    sa.Column('ollama_num_ctx', sa.Integer(), server_default=sa.text('2048'), nullable=False),
    sa.Column('llm_max_tokens', sa.Integer(), nullable=False),
    sa.Column('llm_temperature', sa.Float(), nullable=False),
    sa.Column('llm_top_p', sa.Float(), nullable=False),
    sa.Column('llm_frequency_penalty', sa.Float(), nullable=False),
    sa.Column('llm_presence_penalty', sa.Float(), nullable=False),
    sa.Column('web_search_provider', sa.String(length=50), nullable=False),
    sa.Column('tavily_api_key', sa.String(length=255), nullable=True),
    sa.Column('brave_search_api_key', sa.String(length=255), nullable=True),
    sa.Column('deepgram_api_key', sa.String(length=255), nullable=True),
    sa.Column('tts_provider', sa.String(length=50), nullable=False),
    sa.Column('stt_provider', sa.String(length=50), nullable=False),
    sa.Column('tts_voice', sa.String(length=255), nullable=True),
    sa.Column('tts_enabled', sa.Boolean(), nullable=False),
    sa.Column('openai_tts_model', sa.String(length=50), nullable=True),
    sa.Column('openai_stt_model', sa.String(length=50), nullable=True),
    sa.Column('hypergraph_llm_provider', sa.String(length=50), nullable=True),
    sa.Column('hypergraph_llm_model', sa.String(length=255), nullable=True),
    sa.Column('archive_enabled', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('updated_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['active_connection_id'], ['llm_connections.id'], ),
    sa.ForeignKeyConstraint(['selected_system_prompt_id'], ['system_prompts.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('videomix_scripts',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('project_id', sa.UUID(), nullable=False),
    sa.Column('version', sa.Integer(), nullable=False),
    sa.Column('script_data', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('total_duration', sa.Float(), nullable=True),
    sa.Column('segment_count', sa.Integer(), nullable=True),
    sa.Column('llm_reasoning', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['project_id'], ['videomix_projects.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('chunks',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('document_id', sa.UUID(), nullable=False),
    sa.Column('content', sa.Text(), nullable=False),
    sa.Column('chunk_index', sa.Integer(), nullable=True),
    sa.Column('start_time', sa.Float(), nullable=True),
    sa.Column('end_time', sa.Float(), nullable=True),
    sa.Column('page_number', sa.Integer(), nullable=True),
    sa.Column('embedding', pgvector.sqlalchemy.vector.VECTOR(dim=1024), nullable=True),
    sa.Column('language', sa.String(length=50), nullable=True),
    sa.Column('search_vector', postgresql.TSVECTOR(), nullable=True),
    sa.Column('metadata_', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.ForeignKeyConstraint(['document_id'], ['documents.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('chunks', schema=None) as batch_op:
        batch_op.create_index('ix_chunks_embedding', ['embedding'], unique=False, postgresql_using='hnsw', postgresql_with={'m': 16, 'ef_construction': 64}, postgresql_ops={'embedding': 'vector_cosine_ops'})
        batch_op.create_index('ix_chunks_search_vector', ['search_vector'], unique=False, postgresql_using='gin')

    op.create_table('collection_documents',
    sa.Column('collection_id', sa.UUID(), nullable=False),
    sa.Column('document_id', sa.UUID(), nullable=False),
    sa.ForeignKeyConstraint(['collection_id'], ['collections.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['document_id'], ['documents.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('collection_id', 'document_id', name='uq_collection_document')
    )
    op.create_table('document_sections',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('document_id', sa.UUID(), nullable=False),
    sa.Column('title', sa.String(length=500), nullable=True),
    sa.Column('content', sa.Text(), nullable=True),
    sa.Column('start_page', sa.Integer(), nullable=True),
    sa.Column('end_page', sa.Integer(), nullable=True),
    sa.Column('metadata_', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['document_id'], ['documents.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('document_sections', schema=None) as batch_op:
        batch_op.create_index('ix_document_sections_metadata', ['metadata_'], unique=False, postgresql_using='gin')

    op.create_table('videomix_render_jobs',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('project_id', sa.UUID(), nullable=False),
    sa.Column('script_id', sa.UUID(), nullable=False),
    sa.Column('celery_task_id', sa.String(length=255), nullable=True),
    sa.Column('status', sa.Enum('pending', 'processing', 'completed', 'error', name='renderjobstatusenum'), nullable=False),
    sa.Column('progress_percentage', sa.Integer(), nullable=True),
    sa.Column('error_message', sa.Text(), nullable=True),
    sa.Column('output_filename', sa.String(length=512), nullable=True),
    sa.Column('output_size_bytes', sa.BigInteger(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('completed_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['project_id'], ['videomix_projects.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['script_id'], ['videomix_scripts.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('celery_task_id')
    )
    op.create_table('hyper_edges',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('description', sa.Text(), nullable=False),
    sa.Column('source_document_id', sa.UUID(), nullable=True),
    sa.Column('source_section_id', sa.UUID(), nullable=True),
    sa.Column('source_chunk_id', sa.UUID(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['source_chunk_id'], ['chunks.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['source_document_id'], ['documents.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['source_section_id'], ['document_sections.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('hyper_edge_members',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('hyper_edge_id', sa.UUID(), nullable=False),
    sa.Column('concept_id', sa.UUID(), nullable=False),
    sa.Column('role', sa.String(length=50), nullable=True),
    sa.ForeignKeyConstraint(['concept_id'], ['concepts.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['hyper_edge_id'], ['hyper_edges.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('hyper_edge_members', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_hyper_edge_members_concept_id'), ['concept_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_hyper_edge_members_hyper_edge_id'), ['hyper_edge_id'], unique=False)

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('hyper_edge_members', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_hyper_edge_members_hyper_edge_id'))
        batch_op.drop_index(batch_op.f('ix_hyper_edge_members_concept_id'))

    op.drop_table('hyper_edge_members')
    op.drop_table('hyper_edges')
    op.drop_table('videomix_render_jobs')
    with op.batch_alter_table('document_sections', schema=None) as batch_op:
        batch_op.drop_index('ix_document_sections_metadata', postgresql_using='gin')

    op.drop_table('document_sections')
    op.drop_table('collection_documents')
    with op.batch_alter_table('chunks', schema=None) as batch_op:
        batch_op.drop_index('ix_chunks_search_vector', postgresql_using='gin')
        batch_op.drop_index('ix_chunks_embedding', postgresql_using='hnsw', postgresql_with={'m': 16, 'ef_construction': 64}, postgresql_ops={'embedding': 'vector_cosine_ops'})

    op.drop_table('chunks')
    op.drop_table('videomix_scripts')
    op.drop_table('user_preferences')
    op.drop_table('messages')
    op.drop_table('documents')
    op.drop_table('videomix_projects')
    op.drop_table('user_memories')
    op.drop_table('system_prompts')
    op.drop_table('llm_connections')
    op.drop_table('conversations')
    with op.batch_alter_table('concepts', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_concepts_name'))

    op.drop_table('concepts')
    op.drop_table('collections')

    # Dropping a table does not drop the Postgres ENUM type its column used
    # (autogenerate omits this) - left in place, a later re-upgrade fails
    # with "type already exists". All owning tables are already gone above.
    bind = op.get_bind()
    sa.Enum(name='videomixstatusenum').drop(bind, checkfirst=True)
    sa.Enum(name='renderjobstatusenum').drop(bind, checkfirst=True)
    sa.Enum(name='file_type_enum').drop(bind, checkfirst=True)
    sa.Enum(name='status_enum').drop(bind, checkfirst=True)
    # ### end Alembic commands ###
