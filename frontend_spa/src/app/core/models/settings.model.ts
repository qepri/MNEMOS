export interface OllamaModel {
  name: string;
  model: string;
  modified_at: string;
  size: number;
  digest: string;
  details?: {
    format?: string;
    family?: string;
    families?: string[];
    parameter_size?: string;
    quantization_level?: string;
  };
  vision?: boolean;
  description?: string;
}

export interface ModelsResponse {
  models: OllamaModel[];
}

export interface CurrentModelResponse {
  model: string | null;
  provider: string;
  has_model: boolean;
}

export interface ChatPreferences {
  use_conversation_context: boolean;
  max_context_messages: number;
  selected_system_prompt_id: string | null;
  chunk_size: number;
  chunk_overlap: number;
  whisper_model: string;
  llm_provider?: string;
  openai_api_key?: string;
  anthropic_api_key?: string;
  groq_api_key?: string;
  local_llm_base_url?: string;
  selected_llm_model?: string;
  transcription_provider?: string;
  custom_api_key?: string;
  memory_enabled?: boolean;
  memory_provider?: string;
  memory_llm_model?: string;
  max_memories?: number;
  active_connection_id?: string;
  web_search_provider?: 'duckduckgo' | 'tavily' | 'brave';
  tavily_api_key?: string;
  brave_search_api_key?: string;
  tts_provider?: string;
  stt_provider?: string;
  tts_voice?: string;
  tts_enabled?: boolean;
  openai_tts_model?: string;
  openai_stt_model?: string;
  deepgram_api_key?: string;
  ollama_num_ctx?: number;
  llm_max_tokens?: number;
  llm_temperature?: number;
  llm_top_p?: number;
  llm_frequency_penalty?: number;
  llm_presence_penalty?: number;
}

export interface LLMConnection {
  id: string;
  name: string;
  base_url: string;
  api_key?: string | null;
  default_model?: string;
  models?: string[];
  provider_type: string;
  created_at: string;
  updated_at: string;
}

export interface LLMConnectionsResponse {
  connections: LLMConnection[];
}

export interface UserMemory {
  id: string;
  content: string;
  created_at: string;
}

export interface MemoriesResponse {
  memories: UserMemory[];
  usage: {
    current: number;
    max: number;
  };
}

export interface SystemPrompt {
  id: string;
  title: string;
  content: string;
  is_default: boolean;
  is_editable: boolean;
  created_at: string;
  updated_at?: string;
}

export interface SystemPromptsResponse {
  prompts: SystemPrompt[];
}

export interface Model {
  name: string;
  full_name: string;
  ollama_name: string | null;
  author: string;
  description: string;
  size_gb: number;
  params: string;
  tags: string[];
  capabilities: string[];
  min_ram_gb: number;
  min_vram_gb: number;
  downloads: number;
  likes: number;
  updated_at: string;
  hf_url: string;
  is_hf_only?: boolean;
  vision?: boolean; // New
}

export interface LibrarySearchResponse {
  models: Model[];
  total: number;
  fallback?: boolean;
}

export interface ModelPullRequest {
  model: string;
  display_name?: string;
}

export interface ModelPullResponse {
  task_id: string;
  status: string;
  model: string;
}

export interface PullStatusResponse {
  task_id: string;
  status: string;
  model_name?: string;
  progress_line?: string;
  total?: number;
  completed?: number;
  result?: any;
  error?: string;
}
