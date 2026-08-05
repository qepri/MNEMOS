export interface Document {
  id: string;
  filename: string;
  original_filename: string;
  file_type: 'pdf' | 'audio' | 'video' | 'youtube';
  // Must match the backend's status_enum exactly (app/models/document.py).
  // This was 'failed' for a long time while the backend emitted 'error', so the
  // error badge never rendered - TypeScript can't catch it, the union is an
  // unchecked assertion over JSON. document.model.spec.ts pins the two together.
  status: 'pending' | 'processing' | 'completed' | 'error';
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
  progress?: number;

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

export interface DocumentSection {
  id: string;
  title: string;
  content: string;
  start_page?: number;
  end_page?: number;
  metadata?: any;
}
