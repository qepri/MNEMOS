from app.extensions import db
from sqlalchemy.dialects.postgresql import UUID
import uuid
from datetime import datetime

class LLMConnection(db.Model):
    """
    Represents a user-defined LLM connection (Provider).
    Replacing hardcoded custom provider slots.
    """
    __tablename__ = 'llm_connections'

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = db.Column(db.String(255), nullable=False, unique=True) # e.g. "Cerebras", "Local 2", "DeepSeek"
    
    # Provider Type (mostly for frontend logic/presets, e.g. 'openai', 'anthropic', 'other')
    provider_type = db.Column(db.String(50), default='openai', nullable=False)
    
    # Connection Details
    base_url = db.Column(db.String(512), nullable=True) # e.g. https://api.cerebras.ai/v1
    api_key = db.Column(db.String(512), nullable=True)
    
    # Defaults
    default_model = db.Column(db.String(255), nullable=True) # e.g. llama-3.3-70b
    
    # List of available models for this connection
    models = db.Column(db.JSON, default=list) # e.g. ["llama-3.1-70b", "llama-3.1-8b"]
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            'id': str(self.id),
            'name': self.name,
            'provider_type': self.provider_type,
            'base_url': self.base_url,
            'api_key': self.api_key, # Unmasked for local user convenience per request
            'default_model': self.default_model,
            'models': self.models or [],
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }
