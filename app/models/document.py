from sqlalchemy import Column, String, Text, DateTime, Enum, Integer
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
    file_type = Column(Enum('pdf', 'audio', 'video', 'youtube', 'epub', name='file_type_enum'), nullable=False)
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

    collection = relationship('Collection', backref='documents')


    def to_dict(self):
        return {
            "id": str(self.id),
            "filename": self.filename,
            "original_filename": self.original_filename,
            "file_type": self.file_type,
            "status": self.status,
            "processing_progress": self.processing_progress or 0,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "metadata": self.metadata_,
            "collection_id": str(self.collection_id) if self.collection_id else None,
            "tag": self.tag,
            "stars": self.stars,
            "comment": self.comment
        }
