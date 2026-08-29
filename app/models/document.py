from sqlalchemy import Column, String, Text, DateTime, Enum, Integer, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from datetime import datetime
from uuid import uuid4
from app.extensions import db

class Document(db.Model):
    __tablename__ = 'documents'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    filename = Column(String(255), nullable=False)
    original_filename = Column(String(255))
    # 'text' covers plain-text sources (.txt, .md): content that arrives as
    # text rather than as a document, so there is nothing to parse out of it.
    file_type = Column(Enum('pdf', 'audio', 'video', 'youtube', 'epub', 'text',
                            name='file_type_enum'), nullable=False)
    file_path = Column(String(512))  # Path in storage
    youtube_url = Column(String(512))  # If it is YouTube
    status = Column(Enum('pending', 'processing', 'completed', 'error', name='status_enum'), default='pending')
    error_message = Column(Text)
    processing_progress = Column(Integer, default=0)  # 0-100 percentage for embedding progress
    metadata_ = Column(JSONB)  # Duration, pages, etc. mapped to metadata_ to avoid conflict with metadata attribute
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, onupdate=datetime.utcnow)
    
    chunks = relationship('Chunk', back_populates='document', cascade='all, delete-orphan')

    # New fields for Collections and Library
    collection_id = Column(UUID(as_uuid=True), db.ForeignKey('collections.id'), nullable=True)
    tag = Column(String(255)) # Simple tag for now
    stars = Column(Integer, default=0)
    comment = Column(Text)
    
    # RAG Optimization: Multi-Language
    language = Column(String(50), default='english') # 'english', 'spanish', 'german', etc.
    summary = Column(Text)

    # Tracks which embedding model produced this doc's chunk vectors. Compared
    # against settings.EMBEDDING_MODEL to flag docs needing re-embedding.
    embedding_model_used = Column(String(255), nullable=True)

    # Single-collection FK (backward compat, deprecated)
    collection = relationship('Collection', foreign_keys=[collection_id])

    # Many-to-many via junction table
    collections = relationship('Collection', secondary='collection_documents', back_populates='documents')


    def to_dict(self):
        return {
            "id": str(self.id),
            "filename": self.filename,
            "original_filename": self.original_filename,
            "file_type": self.file_type,
            "youtube_url": self.youtube_url,
            "status": self.status,
            "processing_progress": self.processing_progress or 0,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "metadata": self.metadata_,
            "collection_id": str(self.collection_id) if self.collection_id else None,
            "collection_ids": [str(c.id) for c in self.collections] if self.collections else [],
            "tag": self.tag,
            "stars": self.stars,
            "comment": self.comment,
            "summary": self.summary,
        }
