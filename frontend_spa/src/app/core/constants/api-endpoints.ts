export const ApiEndpoints = {
  // Chat
  CHAT: '/api/chat',

  // Documents
  DOCUMENTS: '/api/documents',
  DOCUMENTS_UPLOAD: '/api/documents/upload',
  DOCUMENT_STATUS: (id: string) => `/api/documents/${id}/status`,
  DOCUMENT_DELETE: (id: string) => `/api/documents/${id}`,
  DOCUMENT_CONTENT: (id: string) => `/api/documents/${id}/content`,

  // Conversations
  CONVERSATIONS: '/api/conversations',
  CONVERSATION_DETAIL: (id: string) => `/api/conversations/${id}`,
  CONVERSATION_DELETE: (id: string) => `/api/conversations/${id}`,

  // Settings
  SETTINGS_MODELS: '/api/settings/models',
  SETTINGS_CURRENT_MODEL: '/api/settings/current-model',
  SETTINGS_CHAT: '/api/settings/chat',
  SETTINGS_PROMPTS: '/api/settings/prompts',
  SETTINGS_PROMPT_DELETE: (id: string) => `/api/settings/prompts/${id}`,
  SETTINGS_PROMPT_UPDATE: (id: string) => `/api/settings/prompts/${id}`,
  SETTINGS_LIBRARY_SEARCH: '/api/settings/library/search',
  SETTINGS_PULL: '/api/settings/pull',
  SETTINGS_PULL_STATUS: (taskId: string) => `/api/settings/pull/status/${taskId}`,
  SETTINGS_PULL_DELETE: (taskId: string) => `/api/settings/pull/${taskId}`,
  SETTINGS_PULL_ACTIVE: '/api/settings/pull/active',
  SETTINGS_HARDWARE: '/api/settings/hardware',
  SETTINGS_CONNECTIONS: '/api/settings/connections',
  SETTINGS_CONNECTION_DELETE: (id: string) => `/api/settings/connections/${id}`,
  SETTINGS_CONNECTION_ACTIVE: '/api/settings/connections/active',

  SETTINGS_FILES: (repoId: string) => `/api/settings/files/${repoId}`,
  SETTINGS_PULL_GGUF: '/api/settings/pull_gguf',
  SETTINGS_DOWNLOADS: '/api/settings/downloads',


  // Ollama Service
  SETTINGS_OLLAMA_STATUS: '/api/settings/ollama/status',
  SETTINGS_OLLAMA_INSTALL: '/api/settings/ollama/install',
  SETTINGS_OLLAMA_START: '/api/settings/ollama/start',

  // Memory
  MEMORY_GET: '/api/memory',
  MEMORY_DELETE: (id: string) => `/api/memory/${id}`,
} as const;
