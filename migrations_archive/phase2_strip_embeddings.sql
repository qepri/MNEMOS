-- Phase 2: Strip unused vector embeddings
-- Run AFTER deploying the updated models (section.py, document.py)

-- Drop indexes first
DROP INDEX IF EXISTS ix_document_sections_embedding;
DROP INDEX IF EXISTS ix_documents_summary_embedding;
DROP INDEX IF EXISTS ix_documents_summary_search_vector;

-- Drop vector columns
ALTER TABLE document_sections DROP COLUMN IF EXISTS embedding;
ALTER TABLE documents DROP COLUMN IF EXISTS summary_embedding;
ALTER TABLE documents DROP COLUMN IF EXISTS summary_search_vector;
ALTER TABLE hyper_edges DROP COLUMN IF EXISTS embedding;
