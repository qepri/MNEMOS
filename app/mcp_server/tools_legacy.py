"""MCP tools: legacy tools kept for backward compatibility."""

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
