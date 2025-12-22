from sqlalchemy import Column, String, Text, Float, Integer, ForeignKey, Index, Computed
from sqlalchemy.dialects.postgresql import UUID, JSONB, TSVECTOR
from sqlalchemy.orm import relationship
from pgvector.sqlalchemy import Vector
from uuid import uuid4
from app.extensions import db
from config.settings import settings

class Chunk(db.Model):
    __tablename__ = 'chunks'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    document_id = Column(UUID(as_uuid=True), ForeignKey('documents.id'), nullable=False)
    content = Column(Text, nullable=False)
    chunk_index = Column(Integer)  # Order of the chunk
    start_time = Column(Float)     # For audio/video (seconds)
    end_time = Column(Float)       # For audio/video
    page_number = Column(Integer)  # For PDFs
    
    # Embedding Dimension from settings
    embedding = Column(Vector(settings.EMBEDDING_DIMENSION)) 
    
    # Full Text Search Vector (Postgres 12+)
    # Using 'spanish' configuration as requested.
    search_vector = Column(TSVECTOR, Computed("to_tsvector('spanish', content)", persisted=True))

    metadata_ = Column(JSONB)
    
    document = relationship('Document', back_populates='chunks')
    
    # Index for vector search: HNSW is faster and more accurate than IVFFlat
    # Index for Full Text Search: GIN
    __table_args__ = (
        Index('ix_chunks_embedding', embedding, postgresql_using='hnsw',
              postgresql_with={'m': 16, 'ef_construction': 64},
              postgresql_ops={'embedding': 'vector_cosine_ops'}),
        Index('ix_chunks_search_vector', search_vector, postgresql_using='gin'),
    )

    def to_dict(self):
        return {
            "id": str(self.id),
            "content": self.content,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "page_number": self.page_number
        }
