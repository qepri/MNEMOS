from sqlalchemy import Column, String, Text, Integer, ForeignKey, Index, DateTime
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from pgvector.sqlalchemy import Vector
from uuid import uuid4
from datetime import datetime
from app.extensions import db
from config.settings import settings

class DocumentSection(db.Model):
    __tablename__ = 'document_sections'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    document_id = Column(UUID(as_uuid=True), ForeignKey('documents.id', ondelete='CASCADE'), nullable=False)
    
    title = Column(String(255))
    content = Column(Text) # The summary of the section
    start_page = Column(Integer)
    end_page = Column(Integer)
    
    # Vector for semantic search (HNSW index applied below)
    embedding = Column(Vector(settings.EMBEDDING_DIMENSION))
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationship
    document = relationship('app.models.document.Document', backref='sections')

    __table_args__ = (
        # HNSW Index for fast vector search
        Index('ix_document_sections_embedding', embedding, postgresql_using='hnsw',
              postgresql_with={'m': 16, 'ef_construction': 64},
              postgresql_ops={'embedding': 'vector_cosine_ops'}),
    )

    def to_dict(self):
        return {
            "id": str(self.id),
            "title": self.title,
            "content": self.content,
            "start_page": self.start_page,
            "end_page": self.end_page
        }
