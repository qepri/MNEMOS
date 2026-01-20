export interface Document {
  id: string;
  filename: string;
  original_filename: string;
  file_type: 'pdf' | 'audio' | 'video' | 'youtube';
  status: 'pending' | 'processing' | 'completed' | 'failed';
  youtube_url?: string;
  file_path?: string;
  error_message?: string;
  created_at: string;
  updated_at?: string;
  metadata?: any;
  collection_id?: string | null;
  tag?: string;
  stars?: number;
  comment?: string;
  summary?: string;

  // UI state
  selected?: boolean;
}

export interface DocumentUploadResponse {
  id: string;
  filename: string;
  original_filename: string;
  file_type: string;
  status: string;
}
