"""MCP tools: settings and utilities."""

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
# PHASE 6: SETTINGS & UTILITIES (LOW-MEDIUM PRIORITY)
# ============================================================================

@mcp.tool()
def get_system_prompts() -> str:
    """
    List all available system prompts (default and custom).

    System prompts control the AI's behavior and personality during searches.

    Returns:
        All system prompts with titles and content previews.

    Example:
        - "What system prompts are available?" → get_system_prompts()
    """
    try:
        with flask_app.app_context():
            prompts = SystemPrompt.query.order_by(
                SystemPrompt.is_default.desc(),
                SystemPrompt.created_at.desc()
            ).all()

            if not prompts:
                return "No system prompts found." + _version_footer()

            output = f"# System Prompts ({len(prompts)})\n\n"

            for prompt in prompts:
                marker = "🔷 [DEFAULT]" if prompt.is_default else "📝 [CUSTOM]"
                output += f"## {marker} {prompt.title}\n\n"
                output += f"- **ID:** {prompt.id}\n"

                content_preview = prompt.content[:200] + "..." if len(prompt.content) > 200 else prompt.content
                output += f"- **Content:** _{content_preview}_\n"

                output += f"- **Editable:** {'Yes' if prompt.is_editable else 'No (System Default)'}\n\n"

            return output + _version_footer()

    except Exception as e:
        return f"Error getting system prompts: {str(e)}" + _version_footer()

@mcp.tool()
def get_active_settings() -> str:
    """
    View current MNEMOS configuration (read-only).

    Shows active LLM provider, model, RAG parameters, and feature flags.
    Useful for troubleshooting or understanding system behavior.

    Returns:
        Current configuration settings.

    Example:
        - "What settings are you using?" → get_active_settings()
    """
    try:
        with flask_app.app_context():
            prefs = UserPreferences.query.first()

            if not prefs:
                return "No preferences configured. Using system defaults." + _version_footer()

            output = f"# Active Settings\n\n"

            output += f"## LLM Configuration\n\n"
            output += f"- **Provider:** {prefs.llm_provider or 'llamacpp'}\n"
            output += f"- **Model:** {prefs.selected_llm_model or 'Not set'}\n"
            output += f"- **Temperature:** {getattr(prefs, 'llm_temperature', 0.7)}\n"
            output += f"- **Max Tokens:** {getattr(prefs, 'llm_max_tokens', 4096)}\n\n"

            output += f"## RAG Configuration\n\n"
            output += f"- **Chunk Size:** {prefs.chunk_size or 1024}\n"
            output += f"- **Chunk Overlap:** {prefs.chunk_overlap or 100}\n\n"

            output += f"## Features\n\n"
            output += f"- **Memory System:** {'Enabled' if getattr(prefs, 'memory_enabled', False) else 'Disabled'}\n"
            output += f"- **Conversation Context:** {'Enabled' if prefs.use_conversation_context else 'Disabled'}\n"
            output += f"- **Max Context Messages:** {prefs.max_context_messages or 10}\n"
            output += f"- **Web Search Provider:** {getattr(prefs, 'web_search_provider', 'duckduckgo')}\n\n"

            output += f"## Other\n\n"
            output += f"- **Whisper Model:** {prefs.whisper_model or 'base'}\n"
            output += f"- **Transcription Provider:** {getattr(prefs, 'transcription_provider', 'local')}\n"

            return output + _version_footer()

    except Exception as e:
        return f"Error getting settings: {str(e)}" + _version_footer()

@mcp.tool()
def reprocess_document_hypergraph(document_id: str) -> str:
    """
    Re-extract knowledge graph concepts and relations from a document.

    Useful after model upgrades or to refine concept extraction.

    Args:
        document_id: UUID of the document to reprocess

    Returns:
        Processing status.

    Example:
        - reprocess_document_hypergraph("doc-uuid")
    """
    try:
        error = _validate_uuid(document_id, "document_id")
        if error:
            return error + _version_footer()

        with flask_app.app_context():
            doc = Document.query.get(document_id)
            if not doc:
                return f"Error: Document {document_id} not found." + _version_footer()

            if doc.status != 'completed':
                return f"Error: Document must be fully processed first. Current status: {doc.status}" + _version_footer()

            from app.tasks.processing import reprocess_hypergraph_task

            # Queue reprocessing
            reprocess_hypergraph_task.delay(document_id)

            output = f"# Hypergraph Reprocessing Started\n\n"
            output += f"- **Document:** {doc.original_filename}\n"
            output += f"- **ID:** {document_id}\n\n"
            output += f"⏳ Knowledge graph extraction started. This may take a few minutes.\n"

            return output + _version_footer()

    except Exception as e:
        return f"Error reprocessing hypergraph: {str(e)}" + _version_footer()

@mcp.tool()
def get_system_stats() -> str:
    """
    Get overview statistics about the knowledge base.

    Returns:
        Total counts of documents, chunks, concepts, collections, and conversations.

    Example:
        - "How big is my knowledge base?" → get_system_stats()
    """
    try:
        with flask_app.app_context():
            from app.models.chunk import Chunk

            doc_count = Document.query.count()
            completed_docs = Document.query.filter_by(status='completed').count()
            chunk_count = Chunk.query.count()
            concept_count = Concept.query.count()
            collection_count = Collection.query.count()
            conversation_count = Conversation.query.count()
            memory_count = UserMemory.query.count()

            # Edge count
            edge_count = HyperEdge.query.count()

            output = f"# MNEMOS Knowledge Base Statistics\n\n"

            output += f"## Documents\n\n"
            output += f"- **Total:** {doc_count}\n"
            output += f"- **Processed:** {completed_docs}\n"
            output += f"- **Pending:** {doc_count - completed_docs}\n\n"

            output += f"## Knowledge Graph\n\n"
            output += f"- **Concepts:** {concept_count}\n"
            output += f"- **Relationships:** {edge_count}\n"
            output += f"- **Chunks:** {chunk_count}\n\n"

            output += f"## Organization\n\n"
            output += f"- **Collections:** {collection_count}\n"
            output += f"- **Conversations:** {conversation_count}\n"
            output += f"- **User Memories:** {memory_count}\n\n"

            # Estimate storage
            avg_chunk_size = 500  # Approximate
            estimated_text_kb = (chunk_count * avg_chunk_size) / 1024

            output += f"## Storage Estimate\n\n"
            output += f"- **Indexed Text:** ~{estimated_text_kb:.1f} KB\n"
            output += f"- **Average Concepts per Document:** {concept_count / completed_docs if completed_docs > 0 else 0:.1f}\n"

            return output + _version_footer()

    except Exception as e:
        return f"Error getting system stats: {str(e)}" + _version_footer()
