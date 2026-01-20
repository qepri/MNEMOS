-- RAG Optimization: Multi-language Support Migration

-- 1. Add Columns to Documents
ALTER TABLE documents ADD COLUMN IF NOT EXISTS summary TEXT;
ALTER TABLE documents ADD COLUMN IF NOT EXISTS summary_embedding vector(1024);
ALTER TABLE documents ADD COLUMN IF NOT EXISTS language VARCHAR(50) DEFAULT 'english';
ALTER TABLE documents ADD COLUMN IF NOT EXISTS summary_search_vector TSVECTOR;

-- 2. Add Columns to Chunks
ALTER TABLE chunks ADD COLUMN IF NOT EXISTS language VARCHAR(50) DEFAULT 'english';
-- Drop old computed column if it exists (might need cascade)
ALTER TABLE chunks DROP COLUMN IF EXISTS search_vector CASCADE;
ALTER TABLE chunks ADD COLUMN search_vector TSVECTOR;

-- 3. Create Trigger Function for Dynamic Language Indexing
CREATE OR REPLACE FUNCTION update_tsvector_by_language() RETURNS TRIGGER AS $$
BEGIN
    -- Map common language codes to Postgres Dictionaries
    -- Default to 'simple' if language is unknown or not supported (e.g., Chinese without plugins)
    DECLARE
        reg_config regconfig;
    BEGIN
        CASE NEW.language
            WHEN 'english' THEN reg_config := 'english'::regconfig;
            WHEN 'spanish' THEN reg_config := 'spanish'::regconfig;
            WHEN 'german' THEN reg_config := 'german'::regconfig;
            WHEN 'french' THEN reg_config := 'french'::regconfig;
            -- Add more mappings as needed
            ELSE reg_config := 'simple'::regconfig;
        END CASE;

        -- Update Summary Vector for Documents
        IF TG_TABLE_NAME = 'documents' THEN
            NEW.summary_search_vector := to_tsvector(reg_config, COALESCE(NEW.summary, ''));
        -- Update Content Vector for Chunks
        ELSIF TG_TABLE_NAME = 'chunks' THEN
            NEW.search_vector := to_tsvector(reg_config, COALESCE(NEW.content, ''));
        END IF;
        
        RETURN NEW;
    exception when others then
        -- Fallback to simple on any error
        IF TG_TABLE_NAME = 'documents' THEN
            NEW.summary_search_vector := to_tsvector('simple', COALESCE(NEW.summary, ''));
        ELSIF TG_TABLE_NAME = 'chunks' THEN
            NEW.search_vector := to_tsvector('simple', COALESCE(NEW.content, ''));
        END IF;
        RETURN NEW;
    END;
END;
$$ LANGUAGE plpgsql;

-- 4. Create Triggers
DROP TRIGGER IF EXISTS tsvector_update_summary ON documents;
CREATE TRIGGER tsvector_update_summary
BEFORE INSERT OR UPDATE ON documents
FOR EACH ROW EXECUTE FUNCTION update_tsvector_by_language();

DROP TRIGGER IF EXISTS tsvector_update_chunk ON chunks;
CREATE TRIGGER tsvector_update_chunk
BEFORE INSERT OR UPDATE ON chunks
FOR EACH ROW EXECUTE FUNCTION update_tsvector_by_language();

-- 5. Create Indexes
CREATE INDEX IF NOT EXISTS ix_documents_summary_embedding 
ON documents USING hnsw (summary_embedding vector_cosine_ops) 
WITH (m = 16, ef_construction = 64);

CREATE INDEX IF NOT EXISTS ix_documents_summary_search_vector 
ON documents USING gin (summary_search_vector);

CREATE INDEX IF NOT EXISTS ix_chunks_search_vector 
ON chunks USING gin (search_vector);

-- 6. Backfill / Update Existing Data
-- Update chunks to use 'spanish' if they were created under the old system (guessing based on previous hardcode)
-- Or just re-save them to trigger the update.
UPDATE documents SET language = 'spanish' WHERE language IS NULL; -- Default assumption for existing? Or 'english'?
UPDATE chunks SET language = 'spanish' WHERE language IS NULL; 

-- Trigger the calculate function for all rows
UPDATE documents SET id = id; 
UPDATE chunks SET id = id;
