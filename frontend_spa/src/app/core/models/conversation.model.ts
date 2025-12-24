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
}

export interface MessageSource {
  document: string;
  text: string;
  score: number;
  location?: string;
  metadata?: any;
}

export interface ConversationDetail {
  conversation: Conversation;
  messages: Message[];
  related_document_ids: string[];
}
