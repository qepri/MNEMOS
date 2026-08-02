"""Shared MCP server context: the FastMCP instance, Flask app and helpers.

Tool modules import from here and register themselves via @mcp.tool(); the
package __init__ imports every module so all tools are registered by the time
the server runs.
"""

try:
    # mcp >= 2.0 renamed FastMCP to MCPServer and moved it. The decorator and
    # run() APIs are compatible, so either import gives the same behaviour.
    from mcp.server.mcpserver import MCPServer as _MCPServer
except ImportError:  # mcp 1.x
    from mcp.server.fastmcp import FastMCP as _MCPServer

from app import create_app

# One Flask app for the process; every tool runs inside its app context.
flask_app = create_app()

mcp = _MCPServer("mnemos-daemon")

VERSION = "2.0"


def _validate_uuid(id_string: str, field_name: str = "ID") -> str | None:
    """Validate UUID format. Returns an error message, or None if valid."""
    import uuid
    try:
        uuid.UUID(id_string)
        return None
    except (ValueError, AttributeError, TypeError):
        return f"Error: Invalid {field_name} format. Expected UUID, got: {id_string}"


def _version_footer() -> str:
    """Footer appended to every tool response."""
    return f"\n\n---\nMNEMOS MCP Server v{VERSION}"


def _format_document(doc) -> str:
    """Format document as human-readable string."""
    return f"{doc.original_filename} ({doc.file_type}) - ID: {doc.id}"
