from mcp.server.fastmcp import FastMCP
from mcp.types import Tool, TextContent
from app.services.rag import RAGService
from app.services.embedder import EmbedderService
from app.models.document import Document
from app.extensions import db
from app import create_app
import asyncio

# In mcp-python-sdk 0.5.0+, FastMCP is the recommended way
# However, to reuse Flask's DB context, we need to be careful.
# This script will likely be run as a standalone process.
# We need to initialize the Flask App to get the DB context.

from config.settings import settings

# Create a minimal app context wrapper
flask_app = create_app()

mcp = FastMCP("mnemos-daemon")

@mcp.tool()
def search_documents(query: str, document_ids: list[str] = None, top_k: int = 5) -> str:
    """
    Busca información en los documentos vectorizados (PDFs, transcripciones de audio/video).
    
    Args:
        query: Pregunta o búsqueda a realizar.
        document_ids: IDs de documentos específicos (opcional).
        top_k: Número de chunks relevantes a usar.
    """
    with flask_app.app_context():
        rag = RAGService(db.session)
        result = rag.query(
            question=query,
            document_ids=document_ids or [],
            top_k=top_k
        )
        
        source_text = "\n".join([f"- {s['document']} ({s['location']})" for s in result['sources']])
        return f"Respuesta: {result['answer']}\n\nFuentes:\n{source_text}"

@mcp.tool()
def list_documents() -> str:
    """Lista todos los documentos disponibles en el sistema con sus IDs."""
    with flask_app.app_context():
        docs = Document.query.filter_by(status='completed').all()
        if not docs:
            return "No ready documents found."
            
        return "\n".join([f"- {d.original_filename} ({d.file_type}) - ID: {d.id}" for d in docs])

if __name__ == "__main__":
    # Ensure tables exist (normally separate migration step)
    mcp.run()
