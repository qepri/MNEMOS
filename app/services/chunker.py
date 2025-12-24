from typing import List
from config.settings import settings
from langchain_text_splitters import RecursiveCharacterTextSplitter

class ChunkerService:
    @staticmethod
    def _get_chunk_settings(default_size: int = None, default_overlap: int = None):
        """Helper to get chunk settings from DB or Config."""
        size = default_size or settings.CHUNK_SIZE
        overlap = default_overlap or settings.CHUNK_OVERLAP
        
        try:
            from app.extensions import db
            from app.models.user_preferences import UserPreferences
            if db.session.registry.has():
                prefs = db.session.query(UserPreferences).first()
                if prefs:
                    size = prefs.chunk_size
                    overlap = prefs.chunk_overlap
        except Exception:
            pass # Fallback to config defaults
            
        return size, overlap

    @staticmethod
    def chunk_text(text: str, chunk_size: int = None, chunk_overlap: int = None) -> List[str]:
        """
        Uses LangChain's RecursiveCharacterTextSplitter for semantic chunking.
        """
        size, overlap = ChunkerService._get_chunk_settings(chunk_size, chunk_overlap)
        
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=size,
            chunk_overlap=overlap,
            separators=["\n\n", "\n", " ", ""],
            length_function=len,
        )
        
        return splitter.split_text(text)

    @staticmethod
    def chunk_transcript_segments(segments: List[dict], chunk_size: int = None) -> List[dict]:
        """
        Merges small Whisper segments into larger chunks while preserving timestamps.
        
        Args:
            segments: List of dicts {'text': str, 'start': float, 'end': float}
            chunk_size: Target characters per chunk (default from settings)
            
        Returns:
            List of dicts {'text': str, 'start': float, 'end': float}
        """
        size, _ = ChunkerService._get_chunk_settings(chunk_size)
        target_size = size
        chunks = []
        
        current_chunk_text = []
        current_start = None
        current_end = None
        current_length = 0
        
        for seg in segments:
            text = seg.get("text", "").strip()
            start = seg.get("start")
            end = seg.get("end")
            
            if not text:
                continue
                
            # Initialize new chunk if needed
            if current_start is None:
                current_start = start
            
            # Simple accumulation strategy
            # (A more advanced version would use a sliding window for overlap)
            current_chunk_text.append(text)
            current_length += len(text) + 1 # +1 for space
            current_end = end # Always update end to current segment's end
            
            if current_length >= target_size:
                # Finalize chunk
                full_text = " ".join(current_chunk_text)
                chunks.append({
                    "text": full_text,
                    "start": current_start,
                    "end": current_end
                })
                
                # Reset
                current_chunk_text = []
                current_start = None
                current_end = None
                current_length = 0
                
        # Handle remainder
        if current_chunk_text:
            full_text = " ".join(current_chunk_text)
            chunks.append({
                "text": full_text,
                "start": current_start,
                "end": current_end
            })
            
        return chunks
