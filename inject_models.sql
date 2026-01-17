-- 1. Ensure a UserPreferences row exists with explicit defaults
INSERT INTO user_preferences (
    id, 
    use_conversation_context,
    max_context_messages,
    chunk_size,
    chunk_overlap,
    whisper_model,
    llm_provider,
    transcription_provider,
    memory_enabled,
    memory_provider,
    max_memories,
    web_search_provider,
    tts_provider,
    stt_provider,
    tts_enabled,
    created_at, 
    updated_at
)
SELECT 
    gen_random_uuid(), -- id
    true, -- use_conversation_context
    10, -- max_context_messages
    512, -- chunk_size
    50, -- chunk_overlap
    'base', -- whisper_model
    'lm_studio', -- llm_provider (will update later)
    'local', -- transcription_provider
    false, -- memory_enabled
    'ollama', -- memory_provider
    50, -- max_memories
    'duckduckgo', -- web_search_provider
    'browser', -- tts_provider
    'browser', -- stt_provider
    false, -- tts_enabled
    NOW(), 
    NOW()
WHERE NOT EXISTS (SELECT 1 FROM user_preferences);

-- 2. Insert the Custom Connection for Mnemos Ollama
INSERT INTO llm_connections (id, name, provider_type, base_url, models, default_model, created_at, updated_at)
VALUES (
    gen_random_uuid(),
    'Mnemos Ollama', 
    'openai',
    'http://mnemos-ollama:11434/v1',
    '["nous-hermes-2-mistral-7b-dpo-gguf-q4_0:latest", "qwen3-8b-hivemind:latest"]'::json,
    'qwen3-8b-hivemind:latest',
    NOW(),
    NOW()
)
ON CONFLICT (name) DO NOTHING;

-- 3. Update UserPreferences to use this new connection
UPDATE user_preferences
SET 
    llm_provider = 'custom',
    active_connection_id = (SELECT id FROM llm_connections WHERE name = 'Mnemos Ollama' LIMIT 1),
    selected_llm_model = 'qwen3-8b-hivemind:latest',
    updated_at = NOW();
