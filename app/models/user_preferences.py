from app.extensions import db
from sqlalchemy.dialects.postgresql import UUID
import uuid
from datetime import datetime

class UserPreferences(db.Model):
    """User preferences for chat behavior."""
    __tablename__ = 'user_preferences'

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    use_conversation_context = db.Column(db.Boolean, default=True, nullable=False)
    max_context_messages = db.Column(db.Integer, default=10, nullable=False)
    selected_system_prompt_id = db.Column(UUID(as_uuid=True), db.ForeignKey('system_prompts.id'), nullable=True)
    
    # RAG Settings
    chunk_size = db.Column(db.Integer, default=512, nullable=False)
    chunk_overlap = db.Column(db.Integer, default=50, nullable=False)
    
    # Persistence
    selected_llm_model = db.Column(db.String(255), nullable=True)
    whisper_model = db.Column(db.String(50), default='base', nullable=False)
    
    # LLM Config (Clean Architecture)
    llm_provider = db.Column(db.String(50), default='lm_studio', nullable=False)
    openai_api_key = db.Column(db.String(255), nullable=True)
    anthropic_api_key = db.Column(db.String(255), nullable=True)
    groq_api_key = db.Column(db.String(255), nullable=True)
    transcription_provider = db.Column(db.String(50), default='local', nullable=False)
    local_llm_base_url = db.Column(db.String(255), default="http://host.docker.internal:1234/v1", nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            'id': str(self.id),
            'use_conversation_context': self.use_conversation_context,
            'max_context_messages': self.max_context_messages,
            'selected_system_prompt_id': str(self.selected_system_prompt_id) if self.selected_system_prompt_id else None,
            'chunk_size': self.chunk_size,
            'chunk_overlap': self.chunk_overlap,
            'selected_llm_model': self.selected_llm_model,
            'whisper_model': self.whisper_model,
            'llm_provider': self.llm_provider,
            'openai_api_key': self.openai_api_key,
            'anthropic_api_key': self.anthropic_api_key,
            "groq_api_key": self.groq_api_key,
            "transcription_provider": self.transcription_provider,
            'local_llm_base_url': self.local_llm_base_url,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }


class SystemPrompt(db.Model):
    """Custom system prompts for RAG."""
    __tablename__ = 'system_prompts'

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = db.Column(db.String(255), nullable=False)
    content = db.Column(db.Text, nullable=False)
    is_default = db.Column(db.Boolean, default=False, nullable=False)
    is_editable = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            'id': str(self.id),
            'title': self.title,
            'content': self.content,
            'is_default': self.is_default,
            'is_editable': self.is_editable,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }
