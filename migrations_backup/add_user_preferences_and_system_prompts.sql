-- Migration: Add user_preferences and system_prompts tables
-- Run this inside the PostgreSQL database

-- Create system_prompts table
CREATE TABLE IF NOT EXISTS system_prompts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title VARCHAR(255) NOT NULL,
    content TEXT NOT NULL,
    is_default BOOLEAN NOT NULL DEFAULT FALSE,
    is_editable BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create user_preferences table
CREATE TABLE IF NOT EXISTS user_preferences (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    use_conversation_context BOOLEAN NOT NULL DEFAULT TRUE,
    max_context_messages INTEGER NOT NULL DEFAULT 10,
    selected_system_prompt_id UUID REFERENCES system_prompts(id) ON DELETE SET NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Insert default system prompt (non-editable)
INSERT INTO system_prompts (title, content, is_default, is_editable)
VALUES (
    'Default RAG Assistant',
    'You are a helpful assistant that answers questions based ONLY on the provided context.
If the information is not in the context, say so.
Always cite the sources using the filename and timestamp/page number when relevant.
Provide detailed and comprehensive answers. Use markdown (bold, lists, headers) to structure your response.',
    TRUE,
    FALSE
) ON CONFLICT DO NOTHING;

-- Create default user preferences
INSERT INTO user_preferences (use_conversation_context, max_context_messages)
VALUES (TRUE, 10)
ON CONFLICT DO NOTHING;

-- Create index for performance
CREATE INDEX IF NOT EXISTS idx_system_prompts_default ON system_prompts(is_default);
