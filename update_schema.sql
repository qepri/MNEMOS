-- Add new columns for Summary Indexing
ALTER TABLE documents ADD COLUMN IF NOT EXISTS summary TEXT;
ALTER TABLE documents ADD COLUMN IF NOT EXISTS summary_embedding vector(1024);

-- Add TSVECTOR column for summary search
ALTER TABLE documents ADD COLUMN IF NOT EXISTS summary_search_vector TSVECTOR 
GENERATED ALWAYS AS (to_tsvector('spanish', summary)) STORED;

-- Add HNSW Index for Vector Search on Summary
CREATE INDEX IF NOT EXISTS ix_documents_summary_embedding 
ON documents USING hnsw (summary_embedding vector_cosine_ops) 
WITH (m = 16, ef_construction = 64);

-- Add GIN Index for Full Text Search on Summary
CREATE INDEX IF NOT EXISTS ix_documents_summary_search_vector 
ON documents USING gin (summary_search_vector);
