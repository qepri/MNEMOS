from app.extensions import db
from sqlalchemy.dialects.postgresql import UUID
import uuid
from datetime import datetime

class UserMemory(db.Model):
    """Stores extracted permanent facts about the user."""
    __tablename__ = 'user_memories'

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    content = db.Column(db.String(512), nullable=False) # The extracted fact
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': str(self.id),
            'content': self.content,
            'created_at': self.created_at.isoformat()
        }
