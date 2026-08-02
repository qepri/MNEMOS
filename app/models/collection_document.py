from app.extensions import db
from sqlalchemy import Column
from sqlalchemy.dialects.postgresql import UUID

# The composite primary key already enforces uniqueness on (collection_id,
# document_id); the live PK carries the name uq_collection_document.
collection_documents = db.Table(
    'collection_documents',
    Column('collection_id', UUID(as_uuid=True), db.ForeignKey('collections.id', ondelete='CASCADE'), primary_key=True),
    Column('document_id', UUID(as_uuid=True), db.ForeignKey('documents.id', ondelete='CASCADE'), primary_key=True),
)
