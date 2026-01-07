export interface Conversation {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
}

export interface Message {
  id: string;
  conversation_id: string;
  role: 'user' | 'assistant';
  content: string;
  sources?: MessageSource[];
  created_at: string;
  status?: 'generating' | 'completed' | 'error';
}

export interface MessageSource {
  document: string;
  document_id?: string;
  page_number?: number;
  start_time?: number;
  end_time?: number;
  text: string;
  file_type?: string;
  youtube_url?: string;
  score: number;
  location?: string;
  metadata?: any;
}

export interface ConversationDetail {
  conversation: Conversation;
  messages: Message[];
  related_document_ids: string[];
}
