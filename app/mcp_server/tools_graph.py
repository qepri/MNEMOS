"""MCP tools: knowledge graph traversal and concept lookup."""

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
    flask_app, mcp, API_BASE, _validate_uuid, _version_footer, _format_document,
)


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
                f"{API_BASE}/api/wiki/search",
                params={'q': query, 'limit': limit},
                timeout=30,
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
                f"{API_BASE}/api/wiki/article/{quote(concept_name)}",
                timeout=30,
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
                f"{API_BASE}/api/wiki/concepts",
                params=params,
                timeout=30,
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
