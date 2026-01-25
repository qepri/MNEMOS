from app.extensions import db
from sqlalchemy import Column, String, Text, DateTime, ForeignKey, Integer
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from pgvector.sqlalchemy import Vector
from config.settings import settings
from datetime import datetime
from uuid import uuid4

class Concept(db.Model):
    __tablename__ = 'concepts'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    name = Column(String(255), unique=True, nullable=False, index=True)
    description = Column(Text)
    embedding = Column(Vector(settings.EMBEDDING_DIMENSION))
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    hyper_edge_members = relationship('HyperEdgeMember', back_populates='concept', cascade='all, delete-orphan')

class HyperEdge(db.Model):
    __tablename__ = 'hyper_edges'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    description = Column(Text, nullable=False) # e.g. "A activates B in context C"
    embedding = Column(Vector(settings.EMBEDDING_DIMENSION))
    
    source_document_id = Column(UUID(as_uuid=True), ForeignKey('documents.id', ondelete='CASCADE'), nullable=True)
    source_section_id = Column(UUID(as_uuid=True), ForeignKey('document_sections.id', ondelete='CASCADE'), nullable=True)
    source_chunk_id = Column(UUID(as_uuid=True), ForeignKey('chunks.id', ondelete='CASCADE'), nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    members = relationship('HyperEdgeMember', back_populates='hyper_edge', cascade='all, delete-orphan')
    document = relationship('app.models.document.Document', backref='hyper_edges')
    chunk = relationship('app.models.chunk.Chunk')

class HyperEdgeMember(db.Model):
    __tablename__ = 'hyper_edge_members'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    hyper_edge_id = Column(UUID(as_uuid=True), ForeignKey('hyper_edges.id', ondelete='CASCADE'), nullable=False, index=True)
    concept_id = Column(UUID(as_uuid=True), ForeignKey('concepts.id', ondelete='CASCADE'), nullable=False, index=True)
    role = Column(String(50)) # optional: "source", "target", "context", etc.
    
    # Relationships
    hyper_edge = relationship('HyperEdge', back_populates='members')
    concept = relationship('Concept', back_populates='hyper_edge_members')
