"""MNEMOS MCP Server - Memory Augmentation Layer.

Entry point only. Tools live in per-domain modules and register themselves
against the shared FastMCP instance on import:

    tools_graph          knowledge graph traversal, concepts
    tools_search         advanced RAG search
    tools_collections    collection organisation
    tools_documents      document management, upload, YouTube
    tools_conversations  conversations and long-term memory
    tools_settings       settings and utilities
    tools_legacy         kept for backward compatibility

Importing this module registers every tool. Tool names and signatures are
unchanged from the previous single-file layout.
"""

from app.mcp_server._shared import flask_app, mcp  # noqa: F401

# Imported for their registration side effects.
from app.mcp_server import (  # noqa: F401,E402
    tools_graph,
    tools_search,
    tools_collections,
    tools_documents,
    tools_conversations,
    tools_settings,
    tools_legacy,
)

if __name__ == "__main__":
    # FastMCP parses its own transport/port args (docker-compose passes
    # `run --transport sse --port 3000 --host 0.0.0.0`).
    mcp.run()
