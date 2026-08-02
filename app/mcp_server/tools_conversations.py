"""MCP tools: conversations and long-term memory."""

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
