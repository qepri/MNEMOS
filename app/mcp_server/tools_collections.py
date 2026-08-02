"""MCP tools: collection organisation."""

import json
import os
import uuid

from app.extensions import db
from app.models.collection import Collection
from app.models.conversation import Conversation, Message
from app.models.document import Document
from app.models.knowledge_graph import Concept, HyperEdge, HyperEdgeMember
from app.models.memory import UserMemory
from app.models.user_preferences import UserPreferences, SystemPrompt
from app.services.embedder import EmbedderService
from app.services.rag import RAGService
from config.settings import settings

from app.mcp_server._shared import (
    flask_app, mcp, _validate_uuid, _version_footer, _format_document,
)


# ============================================================================
# PHASE 3: COLLECTIONS & ORGANIZATION (HIGH PRIORITY)
# ============================================================================

@mcp.tool()
def list_collections() -> str:
    """
    List all document collections with names, descriptions, and document counts.

    Collections help organize documents by topic or project.

    Returns:
        All collections with metadata.

    Example:
        - "What collections do I have?" → list_collections()
    """
    try:
        with flask_app.app_context():
            collections = Collection.query.order_by(Collection.name.asc()).all()

            if not collections:
                return "No collections found. Create one with create_collection." + _version_footer()

            output = f"# Collections ({len(collections)})\n\n"

            for coll in collections:
                doc_count = len(coll.documents) if coll.documents else 0
                output += f"## {coll.name}\n\n"
                output += f"- **ID:** {coll.id}\n"
                output += f"- **Documents:** {doc_count}\n"
                if coll.description:
                    output += f"- **Description:** {coll.description}\n"
                output += "\n"

            return output + _version_footer()

    except Exception as e:
        return f"Error listing collections: {str(e)}" + _version_footer()

@mcp.tool()
def create_collection(name: str, description: str = None) -> str:
    """
    Create a new collection for organizing documents.

    Args:
        name: Collection name (required, must be unique)
        description: Optional description of what this collection contains

    Returns:
        Created collection with ID.

    Examples:
        - create_collection("Machine Learning Papers", "Research papers on ML algorithms")
        - create_collection("Meeting Notes")
    """
    try:
        with flask_app.app_context():
            # Check if name already exists
            existing = Collection.query.filter_by(name=name).first()
            if existing:
                return f"Error: Collection '{name}' already exists (ID: {existing.id})" + _version_footer()

            collection = Collection(name=name, description=description)
            db.session.add(collection)
            db.session.commit()

            output = f"# Collection Created\n\n"
            output += f"- **Name:** {collection.name}\n"
            output += f"- **ID:** {collection.id}\n"
            if description:
                output += f"- **Description:** {description}\n"

            output += f"\n✅ Collection created successfully. Use add_document_to_collection to add documents.\n"

            return output + _version_footer()

    except Exception as e:
        db.session.rollback()
        return f"Error creating collection: {str(e)}" + _version_footer()

@mcp.tool()
def get_collection_documents(collection_id: str) -> str:
    """
    List all documents in a specific collection.

    Args:
        collection_id: UUID of the collection

    Returns:
        Documents with metadata (title, type, ID).

    Example:
        - get_collection_documents("abc-123-def...")
    """
    try:
        error = _validate_uuid(collection_id, "collection_id")
        if error:
            return error + _version_footer()

        with flask_app.app_context():
            collection = Collection.query.get(collection_id)
            if not collection:
                return f"Error: Collection {collection_id} not found. Use list_collections to see available collections." + _version_footer()

            docs = collection.documents

            output = f"# {collection.name}\n\n"
            if collection.description:
                output += f"{collection.description}\n\n"

            output += f"## Documents ({len(docs)})\n\n"

            if not docs:
                output += "_No documents in this collection yet._\n"
            else:
                for doc in docs:
                    output += f"- {_format_document(doc)}\n"

            return output + _version_footer()

    except Exception as e:
        return f"Error getting collection documents: {str(e)}" + _version_footer()

@mcp.tool()
def add_document_to_collection(document_id: str, collection_id: str) -> str:
    """
    Add a document to a collection for organization.

    Args:
        document_id: UUID of the document
        collection_id: UUID of the collection

    Returns:
        Success message.

    Example:
        - add_document_to_collection("doc-uuid", "collection-uuid")
    """
    try:
        error = _validate_uuid(document_id, "document_id")
        if error:
            return error + _version_footer()

        error = _validate_uuid(collection_id, "collection_id")
        if error:
            return error + _version_footer()

        with flask_app.app_context():
            document = Document.query.get(document_id)
            if not document:
                return f"Error: Document {document_id} not found." + _version_footer()

            collection = Collection.query.get(collection_id)
            if not collection:
                return f"Error: Collection {collection_id} not found." + _version_footer()

            if document not in collection.documents:
                collection.documents.append(document)
                db.session.commit()

            output = f"✅ Document added to collection\n\n"
            output += f"- **Document:** {document.original_filename}\n"
            output += f"- **Collection:** {collection.name}\n"

            return output + _version_footer()

    except Exception as e:
        db.session.rollback()
        return f"Error adding document to collection: {str(e)}" + _version_footer()

@mcp.tool()
def remove_document_from_collection(document_id: str, collection_id: str) -> str:
    """
    Remove a document from a specific collection (document remains in system).

    Args:
        document_id: UUID of the document
        collection_id: UUID of the collection to remove from

    Returns:
        Success message.

    Example:
        - remove_document_from_collection("doc-uuid", "collection-uuid")
    """
    try:
        error = _validate_uuid(document_id, "document_id")
        if error:
            return error + _version_footer()

        error = _validate_uuid(collection_id, "collection_id")
        if error:
            return error + _version_footer()

        with flask_app.app_context():
            document = Document.query.get(document_id)
            if not document:
                return f"Error: Document {document_id} not found." + _version_footer()

            collection = Collection.query.get(collection_id)
            if not collection:
                return f"Error: Collection {collection_id} not found." + _version_footer()

            if document not in collection.documents:
                return f"Document {document.original_filename} is not in collection '{collection.name}'." + _version_footer()

            collection.documents.remove(document)
            db.session.commit()

            output = f"✅ Document removed from collection\n\n"
            output += f"- **Document:** {document.original_filename}\n"
            output += f"- **Collection:** {collection.name}\n"

            return output + _version_footer()

    except Exception as e:
        db.session.rollback()
        return f"Error removing document from collection: {str(e)}" + _version_footer()
