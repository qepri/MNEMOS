from app.extensions import db
from app.models.document import Document
from app.models.chunk import Chunk
from app.services.llm_client import get_llm_client, reset_client
from app.services.embedder import EmbedderService
import logging
from uuid import UUID

logger = logging.getLogger(__name__)

class SummaryService:
    @staticmethod
    def generate_summary(document_id: str):
        """
        Generates a summary for the given document ID.
        Fetches chunks, prompts LLM, and saves summary + embedding.
        """
        try:
            logger.info(f"Generating summary logic for doc {document_id}")
            
            # Handle UUID vs String input
            oid = document_id
            if isinstance(document_id, str):
                oid = UUID(document_id)
            
            doc = db.session.get(Document, oid)
            if not doc:
                logger.error(f"Document {document_id} not found for summary")
                return None

            # Fetch chunks for context
            chunks = db.session.query(Chunk).filter_by(document_id=doc.id).order_by(Chunk.chunk_index).limit(10).all()
            if not chunks:
                logger.warning("No chunks found to summarize")
                return None

            summary_context = "\n".join([c.content for c in chunks])[:10000]
            logger.info(f"Generating summary using context length: {len(summary_context)} chars")
            
            # Ensure fresh client
            reset_client()
            llm = get_llm_client()
            
            summary_prompt = f"""Summarize the following text in a detailed paragraph (200-300 words). 
Focus on the main topics, key entities, and core arguments.
Text:
{summary_context}
"""
            summary_text = llm.chat(
                system="You are an expert summarizer.",
                messages=[{"role": "user", "content": summary_prompt}]
            )
            
            logger.info(f"Summary generated: {summary_text[:50]}...")
            
            doc.summary = summary_text
            
            # Embed Summary
            logger.info("Embedding summary...")
            embedder = EmbedderService()
            summary_vec = embedder.embed([summary_text])[0]
            doc.summary_embedding = summary_vec
            
            logger.info("Summary generated and embedded.")
            doc.processing_progress = 85 if doc.processing_progress < 85 else doc.processing_progress
            db.session.commit()
            
            return summary_text

        except Exception as e:
            logger.error(f"Failed to generate summary: {e}")
            raise e
