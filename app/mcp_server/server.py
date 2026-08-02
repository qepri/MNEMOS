"""
MNEMOS MCP Server - Comprehensive Memory Augmentation Layer
Version: 2.0
Description: Exposes full MNEMOS capabilities through Model Context Protocol

Features:
- Knowledge Graph & Reasoning (4 tools)
- Advanced RAG & Search (2 tools)
- Collections & Organization (5 tools)
- Document Management (6 tools)
- Conversations & Memory (6 tools)
- Settings & Utilities (4 tools)
- Legacy Tools (3 tools)

Total: 30 tools + Resources + Prompts
"""

from mcp.server.fastmcp import FastMCP
from mcp.types import Tool, TextContent
from app import create_app
from app.extensions import db
from app.services.rag import RAGService
from app.services.embedder import EmbedderService
from app.models.document import Document
from app.models.collection import Collection
from app.models.conversation import Conversation, Message
from app.models.memory import UserMemory
from app.models.knowledge_graph import Concept, HyperEdge, HyperEdgeMember
from app.models.user_preferences import UserPreferences, SystemPrompt
from config.settings import settings
import json
import uuid
import os

# Create Flask app context wrapper
flask_app = create_app()

# Initialize FastMCP server
mcp = FastMCP("mnemos-daemon")

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def _validate_uuid(id_string: str, field_name: str = "ID") -> str | None:
    """Validate UUID format. Returns error message or None if valid."""
    try:
        uuid.UUID(id_string)
        return None
    except (ValueError, AttributeError, TypeError):
        return f"Error: Invalid {field_name} format. Expected UUID, got: {id_string}"

def _version_footer() -> str:
    """Add version footer to responses."""
    return "\n\n---\nMNEMOS MCP Server v2.0"

def _format_document(doc: Document) -> str:
    """Format document as human-readable string."""
    return f"{doc.original_filename} ({doc.file_type}) - ID: {doc.id}"

# ============================================================================
# PHASE 1: KNOWLEDGE GRAPH & REASONING (CRITICAL PRIORITY)
# ============================================================================

@mcp.tool()
def traverse_concepts(
    start_concept: str,
    goal_concept: str,
    collection_ids: list[str] = None,
    use_semantic_leap: bool = False,
    max_depth: int = 3,
    save_to_chat: bool = False
) -> str:
    """
    Find logical paths between two concepts through the knowledge graph.

    This is MNEMOS's most powerful feature - connecting ideas across documents
    through concept relationships extracted by the hypergraph system.

    Args:
        start_concept: Starting concept name (e.g., "quantum computing")
        goal_concept: Target concept name (e.g., "cryptography")
        collection_ids: Optional filter by document collections
        use_semantic_leap: Enable semantic similarity shortcuts when no direct path exists
        max_depth: Maximum traversal depth (1-5, default 3)
        save_to_chat: Auto-save result as a conversation for future reference

    Returns:
        Narrative explanation of the conceptual path with supporting evidence,
        plus graph visualization data showing nodes and edges.

    Examples:
        - "How does quantum computing relate to cryptography?"
          → traverse_concepts("quantum computing", "cryptography")

        - "Connect machine learning to ethics through my research papers"
          → traverse_concepts("machine learning", "ethics", collection_ids=["research-uuid"])
    """
    try:
        with flask_app.app_context():
            from app.services.reasoning_engine import ReasoningEngine

            engine = ReasoningEngine()
            result = engine.traverse(
                start_concept,
                goal_concept,
                collection_ids=collection_ids or [],
                use_semantic_leap=use_semantic_leap,
                max_depth=max_depth
            )

            # Check if result is error string
            if isinstance(result, str):
                return result + _version_footer()

            # Extract narrative and graph data
            narrative = result.get('narrative', 'No path found')
            graph_data = result.get('graph_data', None)

            # Optionally save to conversation
            conversation_id = None
            if save_to_chat:
                try:
                    title = f"Reasoning: {start_concept} → {goal_concept}"
                    conversation = Conversation(title=title)
                    db.session.add(conversation)
                    db.session.flush()

                    # User message
                    user_msg = Message(
                        conversation_id=conversation.id,
                        role='user',
                        content=f"Find logical path from '{start_concept}' to '{goal_concept}'"
                    )
                    db.session.add(user_msg)

                    # Assistant response with graph data
                    if graph_data:
                        graph_data['search_params'] = {
                            'max_depth': max_depth,
                            'use_semantic_leap': use_semantic_leap
                        }

                    ai_msg = Message(
                        conversation_id=conversation.id,
                        role='assistant',
                        content=narrative,
                        graph_data=graph_data
                    )
                    db.session.add(ai_msg)
                    db.session.commit()
                    conversation_id = str(conversation.id)
                except Exception as e:
                    # Don't fail the whole request if chat save fails
                    pass

            # Format response
            response = f"# Concept Traversal: {start_concept} → {goal_concept}\n\n"
            response += f"**Mode:** {'Semantic Leap' if use_semantic_leap else 'Direct Path'}\n"
            response += f"**Max Depth:** {max_depth}\n\n"
            response += f"## Reasoning\n\n{narrative}\n\n"

            if graph_data:
                response += f"## Graph Structure\n\n{json.dumps(graph_data, indent=2)}\n\n"

            if conversation_id:
                response += f"💾 Saved to conversation: {conversation_id}\n"

            return response + _version_footer()

    except Exception as e:
        return f"Error traversing concepts: {str(e)}" + _version_footer()

@mcp.tool()
def search_concepts(query: str, limit: int = 20) -> str:
    """
    Search for concepts in the knowledge graph using hybrid semantic + keyword search.

    This searches across all concepts extracted from your documents, using both
    prefix matching (fast, deterministic) and vector similarity (semantic).

    Args:
        query: Search query (e.g., "neural", "quantum computing")
        limit: Maximum results to return (default 20)

    Returns:
        Ranked list of concepts with descriptions. Use concept names in
        get_concept_article to explore further.

    Examples:
        - "What concepts relate to 'neural networks'?"
          → search_concepts("neural")

        - "Find all concepts about AI ethics"
          → search_concepts("AI ethics")
    """
    try:
        with flask_app.app_context():
            import requests

            # Call internal wiki API
            response = requests.get(
                f"http://localhost:{settings.PORT or 5000}/api/wiki/search",
                params={'q': query, 'limit': limit}
            )

            if response.status_code != 200:
                return f"Error: Failed to search concepts (status {response.status_code})" + _version_footer()

            data = response.json()
            results = data.get('results', [])

            if not results:
                return f"No concepts found matching '{query}'. Try broader terms or check spelling." + _version_footer()

            # Format results
            output = f"# Concept Search Results for '{query}'\n\n"
            output += f"Found {len(results)} concepts:\n\n"

            for i, concept in enumerate(results, 1):
                name = concept.get('name', 'Unknown')
                desc = concept.get('description', '')
                desc_preview = (desc[:100] + '...') if len(desc) > 100 else desc
                output += f"{i}. **{name}**\n"
                if desc_preview:
                    output += f"   {desc_preview}\n"
                output += f"   _ID: {concept.get('id')}_\n\n"

            output += f"\n💡 Use `get_concept_article(concept_name)` to explore any concept in depth.\n"

            return output + _version_footer()

    except Exception as e:
        return f"Error searching concepts: {str(e)}" + _version_footer()

@mcp.tool()
def get_concept_article(concept_name: str) -> str:
    """
    Retrieve the full article for a specific concept from the knowledge graph.

    Articles include:
    - Concept description
    - All relationships (edges) with other concepts
    - Source citations (which documents/chunks mentioned this)
    - Related concepts for further exploration

    Args:
        concept_name: Name of the concept (exact or fuzzy match)

    Returns:
        Comprehensive article with relations, sources, and related concepts.

    Examples:
        - "What is transformer architecture in my knowledge base?"
          → get_concept_article("transformer architecture")

        - "Deep dive into quantum entanglement"
          → get_concept_article("quantum entanglement")
    """
    try:
        with flask_app.app_context():
            import requests
            from urllib.parse import quote

            # Call internal wiki API
            response = requests.get(
                f"http://localhost:{settings.PORT or 5000}/api/wiki/article/{quote(concept_name)}"
            )

            if response.status_code == 404:
                return f"Concept '{concept_name}' not found. Use search_concepts to find similar concepts." + _version_footer()

            if response.status_code != 200:
                return f"Error: Failed to get article (status {response.status_code})" + _version_footer()

            article = response.json()

            # Format article
            output = f"# {article['name']}\n\n"

            if article.get('description'):
                output += f"{article['description']}\n\n"

            # Relations
            relations = article.get('relations', [])
            if relations:
                output += f"## Relationships ({len(relations)})\n\n"
                for rel in relations:
                    output += f"### {rel['description']}\n"
                    peers = rel.get('peers', [])
                    if peers:
                        output += "Connected to: "
                        output += ", ".join([f"**{p['name']}**" for p in peers])
                        output += "\n"
                    output += "\n"

            # Sources
            sources = article.get('sources', [])
            if sources:
                output += f"## Sources ({len(sources)})\n\n"
                for src in sources[:5]:  # Limit to first 5 sources
                    doc_title = src.get('document_title', 'Unknown')
                    content_preview = src.get('content', '')[:150]
                    output += f"- **{doc_title}**\n"
                    output += f"  _{content_preview}..._\n\n"

                if len(sources) > 5:
                    output += f"_... and {len(sources) - 5} more sources_\n\n"

            # Related concepts
            related = article.get('related', [])
            if related:
                output += f"## Related Concepts ({len(related)})\n\n"
                for rel_concept in related[:10]:
                    output += f"- {rel_concept['name']}\n"

                if len(related) > 10:
                    output += f"\n_... and {len(related) - 10} more_\n"

            return output + _version_footer()

    except Exception as e:
        return f"Error retrieving concept article: {str(e)}" + _version_footer()

@mcp.tool()
def list_concepts(letter: str = None, limit: int = 100, offset: int = 0) -> str:
    """
    Browse all concepts in the knowledge graph alphabetically.

    Args:
        letter: Filter by first letter (a-z) or '#' for non-alphabetic (optional)
        limit: Results per page (default 100)
        offset: Pagination offset (default 0)

    Returns:
        Paginated list of concepts with descriptions.

    Examples:
        - "Show all concepts" → list_concepts()
        - "Concepts starting with 'q'" → list_concepts(letter="q")
        - "Next page" → list_concepts(limit=100, offset=100)
    """
    try:
        with flask_app.app_context():
            import requests

            params = {'limit': limit, 'offset': offset}
            if letter:
                params['letter'] = letter.lower()

            response = requests.get(
                f"http://localhost:{settings.PORT or 5000}/api/wiki/concepts",
                params=params
            )

            if response.status_code != 200:
                return f"Error: Failed to list concepts (status {response.status_code})" + _version_footer()

            data = response.json()
            concepts = data.get('concepts', [])
            total = data.get('total', 0)

            if not concepts:
                return "No concepts found in knowledge graph. Process some documents first." + _version_footer()

            # Format output
            filter_str = f" starting with '{letter}'" if letter else ""
            output = f"# Concepts{filter_str}\n\n"
            output += f"Showing {len(concepts)} of {total} total concepts\n"
            output += f"(Page: {offset // limit + 1})\n\n"

            for concept in concepts:
                name = concept.get('name', 'Unknown')
                desc = concept.get('description', '')
                desc_preview = (desc[:80] + '...') if len(desc) > 80 else desc
                output += f"- **{name}**"
                if desc_preview:
                    output += f": {desc_preview}"
                output += "\n"

            # Pagination hint
            if offset + limit < total:
                output += f"\n_Next page: list_concepts(letter='{letter or ''}', offset={offset + limit})_\n"

            return output + _version_footer()

    except Exception as e:
        return f"Error listing concepts: {str(e)}" + _version_footer()

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

# ============================================================================
# PHASE 5: CONVERSATIONS & MEMORY (MEDIUM-HIGH PRIORITY)
# ============================================================================

@mcp.tool()
def list_conversations(search: str = None, limit: int = 20) -> str:
    """
    Browse conversation history.

    Args:
        search: Optional filter by title (case-insensitive)
        limit: Max results to return (default 20)

    Returns:
        List of conversations with titles, dates, and IDs.

    Examples:
        - "What conversations have we had?" → list_conversations()
        - "Find conversations about quantum" → list_conversations(search="quantum")
    """
    try:
        with flask_app.app_context():
            query = Conversation.query.order_by(Conversation.updated_at.desc())

            if search:
                query = query.filter(Conversation.title.ilike(f'%{search}%'))

            conversations = query.limit(limit).all()

            if not conversations:
                msg = f"No conversations found"
                if search:
                    msg += f" matching '{search}'"
                return msg + "." + _version_footer()

            output = f"# Conversations"
            if search:
                output += f" matching '{search}'"
            output += f" ({len(conversations)})\n\n"

            for conv in conversations:
                msg_count = len(conv.messages) if conv.messages else 0
                output += f"## {conv.title}\n\n"
                output += f"- **ID:** {conv.id}\n"
                output += f"- **Messages:** {msg_count}\n"
                output += f"- **Last Updated:** {conv.updated_at}\n\n"

            return output + _version_footer()

    except Exception as e:
        return f"Error listing conversations: {str(e)}" + _version_footer()

@mcp.tool()
def get_conversation(conversation_id: str) -> str:
    """
    Retrieve full conversation with all messages.

    Args:
        conversation_id: UUID of the conversation

    Returns:
        All messages with roles, content, and timestamps.

    Example:
        - "Show conversation abc-123" → get_conversation("abc-123")
    """
    try:
        error = _validate_uuid(conversation_id, "conversation_id")
        if error:
            return error + _version_footer()

        with flask_app.app_context():
            conversation = Conversation.query.get(conversation_id)
            if not conversation:
                return f"Error: Conversation {conversation_id} not found. Use list_conversations to see available conversations." + _version_footer()

            messages = conversation.messages

            output = f"# {conversation.title}\n\n"
            output += f"**Conversation ID:** {conversation.id}\n"
            output += f"**Created:** {conversation.created_at}\n"
            output += f"**Last Updated:** {conversation.updated_at}\n"
            output += f"**Messages:** {len(messages)}\n\n"

            output += "---\n\n"

            for msg in messages:
                role_icon = "👤" if msg.role == "user" else "🤖"
                output += f"### {role_icon} {msg.role.title()}\n\n"
                output += f"{msg.content}\n\n"

                if msg.sources:
                    output += f"_Sources: {len(msg.sources)} citations_\n\n"

                output += f"_Time: {msg.created_at}_\n\n"
                output += "---\n\n"

            return output + _version_footer()

    except Exception as e:
        return f"Error getting conversation: {str(e)}" + _version_footer()

@mcp.tool()
def search_conversations(query: str, limit: int = 10) -> str:
    """
    Search conversation history by content (semantic search).

    Args:
        query: Search query (searches both titles and message content)
        limit: Max conversations to return (default 10)

    Returns:
        Relevant conversations with context snippets.

    Example:
        - "What did we discuss about transformers?" → search_conversations("transformers")
    """
    try:
        with flask_app.app_context():
            # Search in titles
            conversations = Conversation.query.filter(
                Conversation.title.ilike(f'%{query}%')
            ).order_by(Conversation.updated_at.desc()).limit(limit).all()

            if not conversations:
                # Fallback: search in message content
                from sqlalchemy import or_
                message_matches = Message.query.filter(
                    Message.content.ilike(f'%{query}%')
                ).order_by(Message.created_at.desc()).limit(limit * 3).all()

                # Get unique conversations
                conv_ids = list(set([msg.conversation_id for msg in message_matches]))
                conversations = Conversation.query.filter(
                    Conversation.id.in_(conv_ids)
                ).order_by(Conversation.updated_at.desc()).limit(limit).all()

            if not conversations:
                return f"No conversations found matching '{query}'." + _version_footer()

            output = f"# Conversation Search: '{query}'\n\n"
            output += f"Found {len(conversations)} conversations:\n\n"

            for conv in conversations:
                # Find matching messages
                matching_msgs = [
                    msg for msg in conv.messages
                    if query.lower() in msg.content.lower()
                ]

                output += f"## {conv.title}\n\n"
                output += f"- **ID:** {conv.id}\n"
                output += f"- **Date:** {conv.updated_at}\n"

                if matching_msgs:
                    snippet = matching_msgs[0].content[:200] + "..."
                    output += f"- **Snippet:** _{snippet}_\n"

                output += "\n"

            return output + _version_footer()

    except Exception as e:
        return f"Error searching conversations: {str(e)}" + _version_footer()

@mcp.tool()
def create_conversation(title: str) -> str:
    """
    Create a new conversation thread.

    Args:
        title: Title for the conversation

    Returns:
        Conversation ID for future reference.

    Example:
        - create_conversation("Research on Quantum Computing")
    """
    try:
        with flask_app.app_context():
            conversation = Conversation(title=title)
            db.session.add(conversation)
            db.session.commit()

            output = f"# Conversation Created\n\n"
            output += f"- **Title:** {title}\n"
            output += f"- **ID:** {conversation.id}\n\n"
            output += f"✅ New conversation started. Use this ID to continue the discussion.\n"

            return output + _version_footer()

    except Exception as e:
        db.session.rollback()
        return f"Error creating conversation: {str(e)}" + _version_footer()

@mcp.tool()
def get_user_memories() -> str:
    """
    Access user memories (facts learned about the user from conversations).

    The memory system extracts and stores important facts about you from
    conversations, enabling personalized assistance.

    Returns:
        All memory entries with content.

    Example:
        - "What do you know about me?" → get_user_memories()
    """
    try:
        with flask_app.app_context():
            memories = UserMemory.query.all()

            # Check if memory system is enabled
            prefs = UserPreferences.query.first()
            if prefs and not prefs.memory_enabled:
                return "Memory system is currently disabled. Enable it in settings to start collecting memories." + _version_footer()

            if not memories:
                return "No memories stored yet. As we interact, I'll learn and remember important facts about you." + _version_footer()

            output = f"# User Memories ({len(memories)})\n\n"

            for i, memory in enumerate(memories, 1):
                output += f"{i}. {memory.content}\n"
                output += f"   _ID: {memory.id} | Created: {memory.created_at}_\n\n"

            output += f"\n💡 These memories help personalize responses. Use delete_memory to remove any memory.\n"

            return output + _version_footer()

    except Exception as e:
        return f"Error getting memories: {str(e)}" + _version_footer()

@mcp.tool()
def delete_memory(memory_id: str, confirm: bool = False) -> str:
    """
    Delete a specific memory entry.

    Args:
        memory_id: UUID of the memory to delete
        confirm: Must be True to actually delete (safety flag)

    Returns:
        Success message or confirmation prompt.

    Example:
        - delete_memory("memory-uuid", confirm=True)
    """
    try:
        error = _validate_uuid(memory_id, "memory_id")
        if error:
            return error + _version_footer()

        with flask_app.app_context():
            memory = UserMemory.query.get(memory_id)
            if not memory:
                return f"Error: Memory {memory_id} not found. Use get_user_memories to see available memories." + _version_footer()

            if not confirm:
                output = f"⚠️ **DELETE CONFIRMATION REQUIRED**\n\n"
                output += f"You are about to delete this memory:\n\n"
                output += f"_{memory.content}_\n\n"
                output += f"To proceed, call: delete_memory('{memory_id}', confirm=True)\n"
                return output + _version_footer()

            content = memory.content
            db.session.delete(memory)
            db.session.commit()

            output = f"✅ Memory Deleted\n\n"
            output += f"Removed: _{content}_\n"

            return output + _version_footer()

    except Exception as e:
        db.session.rollback()
        return f"Error deleting memory: {str(e)}" + _version_footer()

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
            output += f"- **Provider:** {prefs.llm_provider or 'ollama'}\n"
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

# ============================================================================
# LEGACY TOOLS (KEEP FOR BACKWARD COMPATIBILITY)
# ============================================================================

@mcp.tool()
def search_documents(query: str, document_ids: list[str] = None, top_k: int = 5) -> str:
    """
    [DEPRECATED] Basic document search. Use search_documents_advanced instead.

    This tool is maintained for backward compatibility but lacks advanced features
    like graph-RAG, web search, and multimodal support.

    Args:
        query: Search question
        document_ids: Optional document filter
        top_k: Number of chunks

    Returns:
        Answer with sources.
    """
    # Redirect to advanced version with deprecation notice
    result = search_documents_advanced(
        query=query,
        document_ids=document_ids,
        top_k=top_k
    )

    deprecation_msg = "⚠️ **DEPRECATED:** This tool will be removed in v3.0. Use search_documents_advanced for full features.\n\n"

    return deprecation_msg + result

@mcp.tool()
def list_documents() -> str:
    """
    List all completed documents with IDs.

    Returns:
        Simple list of documents with filenames, types, and IDs.

    Example:
        - "What documents do I have?" → list_documents()
    """
    try:
        with flask_app.app_context():
            docs = Document.query.filter_by(status='completed').order_by(
                Document.created_at.desc()
            ).all()

            if not docs:
                return "No completed documents found. Upload documents with upload_document or add_youtube_video." + _version_footer()

            output = f"# Documents ({len(docs)})\n\n"

            for doc in docs:
                output += f"- {_format_document(doc)}\n"
                if doc.collections:
                    coll_names = ", ".join(c.name for c in doc.collections)
                    output += f"  _Collections: {coll_names}_\n"

            output += f"\n💡 Use get_document_details(id) for full information about any document.\n"

            return output + _version_footer()

    except Exception as e:
        return f"Error listing documents: {str(e)}" + _version_footer()

@mcp.tool()
def generate_pdf_report(markdown_content: str, filename: str = "report") -> str:
    """
    Generate a PDF file from Markdown content.

    Useful for saving research reports, summaries, or essays generated during
    conversations.

    Args:
        markdown_content: Text content in Markdown format
        filename: Desired filename without extension (default "report")

    Returns:
        File path to generated PDF.

    Example:
        - generate_pdf_report("# My Research\\n\\nContent here...", "quantum_research")
    """
    try:
        import markdown2
        from xhtml2pdf import pisa

        # Convert Markdown to HTML
        html_content = markdown2.markdown(markdown_content)

        styled_html = f"""
        <html>
        <head>
            <style>
                body {{ font-family: Helvetica, sans-serif; padding: 40px; line-height: 1.5; }}
                h1 {{ color: #333; border-bottom: 2px solid #333; padding-bottom: 10px; }}
                h2 {{ color: #444; margin-top: 20px; }}
                p {{ margin-bottom: 15px; text-align: justify; }}
                blockquote {{ background: #f9f9f9; border-left: 5px solid #ccc; margin: 1.5em 10px; padding: 0.5em 10px; }}
                code {{ background: #f0f0f0; padding: 2px 5px; border-radius: 3px; }}
                pre {{ background: #f0f0f0; padding: 10px; border-radius: 5px; overflow-x: auto; }}
            </style>
        </head>
        <body>
            {html_content}
        </body>
        </html>
        """

        # Define output path
        output_dir = "/app/uploads/reports"
        os.makedirs(output_dir, exist_ok=True)

        safe_filename = "".join([c for c in filename if c.isalpha() or c.isdigit() or c in (' ', '-', '_')]).rstrip()
        if not safe_filename:
            safe_filename = "report"

        output_path = f"{output_dir}/{safe_filename}.pdf"

        # Generate PDF
        with open(output_path, "wb") as pdf_file:
            pisa_status = pisa.CreatePDF(styled_html, dest=pdf_file)

        if pisa_status.err:
            return f"Error creating PDF: {pisa_status.err}" + _version_footer()

        output = f"# PDF Generated\n\n"
        output += f"- **Filename:** {safe_filename}.pdf\n"
        output += f"- **Path:** {output_path}\n\n"
        output += f"✅ PDF saved to server's reports directory.\n"

        return output + _version_footer()

    except Exception as e:
        return f"Error generating PDF: {str(e)}" + _version_footer()

# ============================================================================
# MCP SERVER ENTRY POINT
# ============================================================================

if __name__ == "__main__":
    import sys

    # FastMCP's run() method doesn't support transport/port args directly
    # It uses its own CLI parser internally
    # The docker-compose command passes: run --transport sse --port 3000 --host 0.0.0.0
    # FastMCP will handle these args automatically
    mcp.run()
