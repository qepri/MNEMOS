"""MCP tools: advanced RAG search."""

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
# PHASE 2: ADVANCED RAG & SEARCH (HIGH PRIORITY)
# ============================================================================

@mcp.tool()
def search_documents_advanced(
    query: str,
    document_ids: list[str] = None,
    collection_ids: list[str] = None,
    top_k: int = 10,
    use_graph_rag: bool = False,
    web_search: bool = False,
    images: list[str] = None
) -> str:
    """
    Advanced document search with full RAG capabilities.

    Features:
    - Hybrid search (vector + keyword)
    - Graph-RAG mode (uses knowledge graph for enhanced retrieval)
    - Web search augmentation
    - Multimodal support (text + images)
    - Conversation context awareness

    Args:
        query: Search question or query
        document_ids: Filter by specific document UUIDs (optional)
        collection_ids: Filter by collection UUIDs (optional)
        top_k: Number of relevant chunks to retrieve (default 10)
        use_graph_rag: Enable graph-based retrieval for conceptual connections
        web_search: Augment with web search results
        images: Base64-encoded images for multimodal queries (optional)

    Returns:
        Answer with sources, citations, and optional web search queries used.

    Examples:
        - "What does my research say about transformers?"
          → search_documents_advanced("transformers", collection_ids=["research-uuid"])

        - "Explain this diagram" (with image)
          → search_documents_advanced("explain", images=["base64..."])

        - "Latest developments in quantum computing"
          → search_documents_advanced("quantum computing", web_search=True)
    """
    try:
        with flask_app.app_context():
            # Resolve collection_ids to document_ids
            all_doc_ids = set(document_ids or [])

            if collection_ids:
                for coll_id in collection_ids:
                    error = _validate_uuid(coll_id, "collection_id")
                    if error:
                        return error + _version_footer()

                    collection = Collection.query.get(coll_id)
                    if collection:
                        all_doc_ids.update([str(d.id) for d in collection.documents])

            # Validate document IDs
            for doc_id in all_doc_ids:
                error = _validate_uuid(doc_id, "document_id")
                if error:
                    return error + _version_footer()

            # Execute RAG query
            rag = RAGService(db.session)
            result = rag.query(
                question=query,
                document_ids=list(all_doc_ids) if all_doc_ids else None,
                top_k=top_k,
                use_graph_rag=use_graph_rag,
                web_search=web_search,
                images=images
            )

            # Format response
            output = f"# Search Results\n\n"
            output += f"**Query:** {query}\n"
            output += f"**Mode:** "
            modes = []
            if use_graph_rag:
                modes.append("Graph-RAG")
            if web_search:
                modes.append("Web Search")
            if images:
                modes.append(f"Multimodal ({len(images)} images)")
            output += ", ".join(modes) if modes else "Standard"
            output += "\n\n"

            # Answer
            output += f"## Answer\n\n{result['answer']}\n\n"

            # Sources
            sources = result.get('sources', [])
            if sources:
                output += f"## Sources ({len(sources)})\n\n"
                doc_sources = [s for s in sources if s.get('type') != 'web']
                web_sources = [s for s in sources if s.get('type') == 'web']

                if doc_sources:
                    output += "### Document Sources\n\n"
                    for src in doc_sources[:10]:
                        output += f"- **{src.get('document', 'Unknown')}** {src.get('location', '')}\n"

                if web_sources:
                    output += "\n### Web Sources\n\n"
                    for src in web_sources:
                        output += f"- [{src.get('title', 'Web Source')}]({src.get('url', '#')})\n"

            # Search queries used (if web search)
            search_queries = result.get('search_queries', [])
            if search_queries:
                output += f"\n### Web Queries Used\n\n"
                for sq in search_queries:
                    output += f"- {sq}\n"

            # Context warning
            if result.get('context_warning'):
                output += f"\n⚠️ {result['context_warning']}\n"

            return output + _version_footer()

    except Exception as e:
        return f"Error searching documents: {str(e)}" + _version_footer()
