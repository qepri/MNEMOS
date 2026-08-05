export const ApiEndpoints = {
  // Chat
  CHAT: '/api/chat',
  CHAT_STREAM: '/api/chat/stream',

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

  // Collections
  COLLECTIONS: '/api/collections',
  COLLECTION_DETAIL: (id: string) => `/api/collections/${id}`,

  // Settings
  SETTINGS_MODELS: '/api/settings/models',
  SETTINGS_CURRENT_MODEL: '/api/settings/current-model',
  SETTINGS_CHAT: '/api/settings/chat',
  SETTINGS_PROMPTS: '/api/settings/prompts',
  SETTINGS_PROMPT_DELETE: (id: string) => `/api/settings/prompts/${id}`,
  SETTINGS_PROMPT_UPDATE: (id: string) => `/api/settings/prompts/${id}`,
  SETTINGS_LIBRARY_SEARCH: '/api/settings/library/search',
  SETTINGS_PULL_STATUS: (taskId: string) => `/api/settings/pull/status/${taskId}`,
  SETTINGS_PULL_DELETE: (taskId: string) => `/api/settings/pull/${taskId}`,
  SETTINGS_PULL_ACTIVE: '/api/settings/pull/active',
  SETTINGS_HARDWARE: '/api/settings/hardware',
  SETTINGS_LLM_AVAILABILITY: '/api/settings/llm-availability',
  SETTINGS_CONNECTIONS: '/api/settings/connections',
  SETTINGS_CONNECTION_DELETE: (id: string) => `/api/settings/connections/${id}`,
  SETTINGS_CONNECTION_ACTIVE: '/api/settings/connections/active',

  SETTINGS_FILES: (repoId: string) => `/api/settings/files/${repoId}`,
  SETTINGS_PULL_GGUF: '/api/settings/pull_gguf',
  SETTINGS_DOWNLOADS: '/api/settings/downloads',


  MEMORY_GET: '/api/memory',
  MEMORY_DELETE: (id: string) => `/api/memory/${id}`,

  // Reasoning
  REASONING_TRAVERSE: '/api/reasoning/traverse',
  REASONING_REPROCESS: '/api/reasoning/reprocess',

  // Wiki
  WIKI_CONCEPTS: '/api/wiki/concepts',
  WIKI_ARTICLE: (name: string) => `/api/wiki/article/${encodeURIComponent(name)}`,
  WIKI_SEARCH: '/api/wiki/search',

  // VideoMix
  VIDEOMIX_PROJECTS: '/api/videomix/projects',
  VIDEOMIX_PROJECT: (id: string) => `/api/videomix/projects/${id}`,
  VIDEOMIX_PROJECT_DELETE: (id: string) => `/api/videomix/projects/${id}`,
  VIDEOMIX_GENERATE_SCRIPT: (projectId: string) => `/api/videomix/projects/${projectId}/generate-script`,
  VIDEOMIX_REFINE_SCRIPT: (projectId: string) => `/api/videomix/projects/${projectId}/refine-script`,
  VIDEOMIX_RENDER_SCRIPT: (scriptId: string) => `/api/videomix/scripts/${scriptId}/render`,
  VIDEOMIX_RENDER_JOB: (jobId: string) => `/api/videomix/render-jobs/${jobId}`,
  VIDEOMIX_CANCEL_RENDER: (jobId: string) => `/api/videomix/render-jobs/${jobId}/cancel`,
  VIDEOMIX_DOWNLOAD: (jobId: string) => `/api/videomix/render-jobs/${jobId}/download`,
} as const;
