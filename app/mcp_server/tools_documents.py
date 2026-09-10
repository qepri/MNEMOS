"""MCP tools: document management."""

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
# PHASE 4: DOCUMENT MANAGEMENT (HIGH PRIORITY)
# ============================================================================

@mcp.tool()
def get_document_details(document_id: str) -> str:
    """
    Get full metadata and details for a specific document.

    Args:
        document_id: UUID of the document

    Returns:
        Complete document information including title, type, status,
        summary, metadata, and collection membership.

    Example:
        - get_document_details("doc-uuid")
    """
    try:
        error = _validate_uuid(document_id, "document_id")
        if error:
            return error + _version_footer()

        with flask_app.app_context():
            doc = Document.query.get(document_id)
            if not doc:
                return f"Error: Document {document_id} not found. Use list_documents to see available documents." + _version_footer()

            output = f"# {doc.original_filename}\n\n"

            output += f"## Basic Information\n\n"
            output += f"- **ID:** {doc.id}\n"
            output += f"- **Type:** {doc.file_type}\n"
            output += f"- **Status:** {doc.status}\n"
            output += f"- **Created:** {doc.created_at}\n"

            if doc.collection:
                output += f"- **Collection:** {doc.collection.name}\n"

            if doc.tag:
                output += f"- **Tag:** {doc.tag}\n"

            if doc.stars:
                output += f"- **Rating:** {'⭐' * doc.stars}\n"

            # Summary
            if doc.summary:
                output += f"\n## Summary\n\n{doc.summary}\n\n"

            # Metadata
            if doc.metadata_:
                output += f"## Metadata\n\n"
                for key, value in doc.metadata_.items():
                    output += f"- **{key.title()}:** {value}\n"
                output += "\n"

            # Processing info
            if doc.processing_progress:
                output += f"**Processing Progress:** {doc.processing_progress}%\n"

            if doc.error_message:
                output += f"⚠️ **Error:** {doc.error_message}\n"

            return output + _version_footer()

    except Exception as e:
        return f"Error getting document details: {str(e)}" + _version_footer()

@mcp.tool()
def get_document_sections(document_id: str) -> str:
    """
    Get hierarchical section structure (table of contents) for a document.

    Useful for navigating large documents like books or research papers.

    Args:
        document_id: UUID of the document

    Returns:
        Section hierarchy with titles and page ranges.

    Example:
        - "Show me the table of contents" → get_document_sections("doc-uuid")
    """
    try:
        error = _validate_uuid(document_id, "document_id")
        if error:
            return error + _version_footer()

        with flask_app.app_context():
            from app.models.section import DocumentSection

            doc = Document.query.get(document_id)
            if not doc:
                return f"Error: Document {document_id} not found." + _version_footer()

            sections = DocumentSection.query.filter_by(document_id=document_id).order_by(
                DocumentSection.start_page
            ).all()

            output = f"# Table of Contents: {doc.original_filename}\n\n"

            if not sections:
                output += "_No sections extracted. This document may not have a structured TOC._\n"
            else:
                for section in sections:
                    page_range = f"[pp. {section.start_page}"
                    if section.end_page and section.end_page != section.start_page:
                        page_range += f"-{section.end_page}"
                    page_range += "]"

                    output += f"- **{section.title}** {page_range}\n"

            return output + _version_footer()

    except Exception as e:
        return f"Error getting document sections: {str(e)}" + _version_footer()

@mcp.tool()
def get_document_summary(document_id: str) -> str:
    """
    Get AI-generated summary of a document.

    Args:
        document_id: UUID of the document

    Returns:
        Comprehensive document summary.

    Example:
        - get_document_summary("doc-uuid")
    """
    try:
        error = _validate_uuid(document_id, "document_id")
        if error:
            return error + _version_footer()

        with flask_app.app_context():
            doc = Document.query.get(document_id)
            if not doc:
                return f"Error: Document {document_id} not found." + _version_footer()

            if not doc.summary:
                return f"No summary available for {doc.original_filename}. Summary may be generating or failed." + _version_footer()

            output = f"# Summary: {doc.original_filename}\n\n"
            output += f"{doc.summary}\n"

            return output + _version_footer()

    except Exception as e:
        return f"Error getting document summary: {str(e)}" + _version_footer()

@mcp.tool()
def upload_document(file_path: str, file_type: str = "auto", collection_id: str = None) -> str:
    """
    Upload a new document to the knowledge base.

    ⚠️ NOTE: This requires file system access. File must be accessible from MCP server.

    Args:
        file_path: Absolute path to the file
        file_type: Type hint (pdf, audio, video, epub, or "auto" for detection)
        collection_id: Optional UUID of collection to add document to

    Returns:
        Document ID and processing status.

    Example:
        - upload_document("/path/to/paper.pdf", collection_id="research-uuid")
    """
    try:
        if not os.path.exists(file_path):
            return f"Error: File not found at {file_path}" + _version_footer()

        if collection_id:
            error = _validate_uuid(collection_id, "collection_id")
            if error:
                return error + _version_footer()

        with flask_app.app_context():
            from werkzeug.utils import secure_filename
            from uuid import uuid4
            from app.tasks.processing import process_document_task

            filename = os.path.basename(file_path)
            safe_name = secure_filename(filename)
            unique_name = f"{uuid4().hex}_{safe_name}"

            # Detect file type
            if file_type == "auto":
                ext = filename.rsplit('.', 1)[-1].lower()
                type_map = {
                    'pdf': 'pdf',
                    'epub': 'epub',
                    'mp3': 'audio', 'wav': 'audio', 'm4a': 'audio',
                    'mp4': 'video', 'webm': 'video', 'mov': 'video'
                }
                file_type = type_map.get(ext, 'pdf')

            # Create document
            doc = Document(
                filename=unique_name,
                original_filename=filename,
                file_type=file_type,
                status='pending',
                collection_id=collection_id
            )

            # Copy file to uploads
            dest_path = os.path.join(settings.UPLOAD_FOLDER, unique_name)
            import shutil
            shutil.copy2(file_path, dest_path)
            doc.file_path = unique_name

            db.session.add(doc)
            db.session.flush()

            # Also add to M2M junction
            if collection_id:
                coll = Collection.query.get(collection_id)
                if coll and doc not in coll.documents:
                    coll.documents.append(doc)

            db.session.commit()

            # Queue processing
            process_document_task.delay(str(doc.id))

            output = f"# Document Upload Started\n\n"
            output += f"- **Filename:** {filename}\n"
            output += f"- **ID:** {doc.id}\n"
            output += f"- **Type:** {file_type}\n"
            output += f"- **Status:** Processing started\n"

            if collection_id:
                coll = Collection.query.get(collection_id)
                output += f"- **Collection:** {coll.name if coll else 'Unknown'}\n"

            output += f"\n⏳ Document is being processed. Use get_document_details to check status.\n"

            return output + _version_footer()

    except Exception as e:
        return f"Error uploading document: {str(e)}" + _version_footer()

@mcp.tool()
def add_youtube_video(youtube_url: str, collection_id: str = None) -> str:
    """
    Download and process a YouTube video (audio transcription + RAG indexing).

    Args:
        youtube_url: Full YouTube URL (e.g., https://youtube.com/watch?v=...)
        collection_id: Optional UUID of collection to add to

    Returns:
        Document ID and processing status.

    Example:
        - add_youtube_video("https://youtube.com/watch?v=dQw4w9WgXcQ")
    """
    try:
        if not youtube_url.startswith('http'):
            return f"Error: Invalid YouTube URL. Must start with http/https." + _version_footer()

        if collection_id:
            error = _validate_uuid(collection_id, "collection_id")
            if error:
                return error + _version_footer()

        with flask_app.app_context():
            from uuid import uuid4
            from app.tasks.processing import process_document_task

            # Create document entry
            doc = Document(
                filename=f"youtube_{uuid4().hex[:8]}",
                original_filename=youtube_url,
                file_type='youtube',
                youtube_url=youtube_url,
                status='pending',
                collection_id=collection_id
            )

            db.session.add(doc)
            db.session.flush()

            # Also add to M2M junction
            if collection_id:
                coll = Collection.query.get(collection_id)
                if coll and doc not in coll.documents:
                    coll.documents.append(doc)

            db.session.commit()

            # Queue processing
            process_document_task.delay(str(doc.id))

            output = f"# YouTube Video Added\n\n"
            output += f"- **URL:** {youtube_url}\n"
            output += f"- **ID:** {doc.id}\n"
            output += f"- **Status:** Download and processing started\n"

            if collection_id:
                coll = Collection.query.get(collection_id)
                output += f"- **Collection:** {coll.name if coll else 'Unknown'}\n"

            output += f"\n⏳ Video is being downloaded and transcribed. Use get_document_details to check progress.\n"

            return output + _version_footer()

    except Exception as e:
        return f"Error adding YouTube video: {str(e)}" + _version_footer()

@mcp.tool()
def delete_document(document_id: str, confirm: bool = False) -> str:
    """
    Delete a document from the system (DESTRUCTIVE - requires confirmation).

    Args:
        document_id: UUID of the document to delete
        confirm: Must be True to actually delete (safety flag)

    Returns:
        Success message or confirmation prompt.

    Example:
        - delete_document("doc-uuid", confirm=True)
    """
    try:
        error = _validate_uuid(document_id, "document_id")
        if error:
            return error + _version_footer()

        with flask_app.app_context():
            doc = Document.query.get(document_id)
            if not doc:
                return f"Error: Document {document_id} not found." + _version_footer()

            if not confirm:
                output = f"⚠️ **DELETE CONFIRMATION REQUIRED**\n\n"
                output += f"You are about to delete:\n"
                output += f"- **Document:** {doc.original_filename}\n"
                output += f"- **Type:** {doc.file_type}\n"
                output += f"- **ID:** {doc.id}\n\n"
                output += f"This will permanently remove the document, its chunks, and knowledge graph entries.\n\n"
                output += f"To proceed, call: delete_document('{document_id}', confirm=True)\n"
                return output + _version_footer()

            # Delete file from disk
            if doc.file_path and not doc.file_path.startswith('youtube_'):
                full_path = os.path.join(settings.UPLOAD_FOLDER, doc.file_path)
                if os.path.exists(full_path):
                    try:
                        os.remove(full_path)
                    except Exception as e:
                        pass  # Continue even if file delete fails

            # Delete from DB (cascades to chunks and graph entries)
            filename = doc.original_filename
            db.session.delete(doc)
            db.session.commit()

            output = f"✅ Document Deleted\n\n"
            output += f"- **Document:** {filename}\n"
            output += f"- **ID:** {document_id}\n\n"
            output += f"The document and all associated data have been permanently removed.\n"

            return output + _version_footer()

    except Exception as e:
        db.session.rollback()
        return f"Error deleting document: {str(e)}" + _version_footer()


@mcp.tool()
def get_document_chunks(
    document_id: str,
    center: int = 0,
    before: int = 5,
    after: int = 5,
) -> str:
    """
    Read a window of a document's text around a given chunk index.

    A document's chunks, in chunk_index order, reconstruct its full text. This
    returns the `center` chunk plus `before`/`after` neighbours, so you can read
    the passage in context (and page through the document by moving `center`).
    Useful for formats with no page view (EPUB, plain text). No LLM involved.

    Args:
        document_id: UUID of the document
        center: chunk_index to center the window on
        before: neighbours to include before center (0-20, default 5)
        after: neighbours to include after center (0-20, default 5)

    Returns:
        The chunks in order, each with its index and location, plus whether
        more text exists before/after the returned window.
    """
    try:
        with flask_app.app_context():
            error = _validate_uuid(document_id, "document_id")
            if error:
                return error + _version_footer()

            from app.models.chunk import Chunk
            from sqlalchemy import select, func

            doc = Document.query.get(document_id)
            if not doc:
                return f"Document {document_id} not found." + _version_footer()

            before = min(max(int(before), 0), 20)
            after = min(max(int(after), 0), 20)
            lo, hi = center - before, center + after

            rows = db.session.execute(
                select(Chunk)
                .where(Chunk.document_id == document_id)
                .where(Chunk.chunk_index >= lo)
                .where(Chunk.chunk_index <= hi)
                .order_by(Chunk.chunk_index)
            ).scalars().all()

            min_idx, max_idx = db.session.execute(
                select(func.min(Chunk.chunk_index), func.max(Chunk.chunk_index))
                .where(Chunk.document_id == document_id)
            ).one()

            title = doc.original_filename or doc.filename
            output = f"# {title}\n\n"
            if not rows:
                output += f"_No chunks in range around index {center}._\n"
                return output + _version_footer()

            if min_idx is not None and lo > min_idx:
                output += "_(earlier text exists — lower `center` to read it)_\n\n"
            for c in rows:
                loc = ""
                if c.page_number is not None:
                    loc = f" [p.{c.page_number}]"
                elif c.start_time is not None:
                    loc = f" [@{int(c.start_time)}s]"
                output += f"### chunk {c.chunk_index}{loc}\n\n{c.content}\n\n"
            if max_idx is not None and hi < max_idx:
                output += "_(more text follows — raise `center` to read it)_\n"

            return output + _version_footer()

    except Exception as e:
        return f"Error reading document chunks: {str(e)}" + _version_footer()
