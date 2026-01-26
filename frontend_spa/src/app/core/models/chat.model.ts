import { MessageSource } from './conversation.model';

export interface ChatRequest {
  question: string;
  document_ids?: string[];
  conversation_id?: string;
  web_search?: boolean;
  use_graph_rag?: boolean;
  images?: string[];
}

export interface ChatResponse {
  answer: string;
  sources: MessageSource[];
  conversation_id: string;
  context_warning?: string;
  search_queries?: string[];
}
