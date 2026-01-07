from pgvector.sqlalchemy import Vector
from sqlalchemy import select, text
from typing import List, Dict
from app.models.chunk import Chunk
from app.models.document import Document
from app.services.embedder import EmbedderService
from app.services.llm_client import get_llm_client

class RAGService:
    def __init__(self, db_session):
        self.db = db_session
        self.embedder = EmbedderService()
        self.llm = get_llm_client()
    
    def search_similar_chunks(
        self, 
        query: str, 
        document_ids: List[str] = None,
        top_k: int = 5
    ) -> List[Chunk]:
        """
        Hybrid search on chunks (Vector + Full Text).
        Combines Cosine Similarity (70%) and Keyword Rank (30%).
        """
        from sqlalchemy import func, desc
        
        query_embedding = self.embedder.embed(query)
        
        # 1. Similarity Score (1 - Distance)
        # Cosine distance is usually 0 (same) to 2 (opposite).
        # We want similarity: 1.0 is match, 0.0 is orthogonal/opposite.
        similarity = 1 - Chunk.embedding.cosine_distance(query_embedding)
        
        # 2. Keyword Score (TS Rank)
        # websearch_to_tsquery handles natural language better than plain to_tsquery
        kw_query = func.websearch_to_tsquery('spanish', query)
        rank = func.ts_rank_cd(Chunk.search_vector, kw_query)
        
        # 3. Hybrid Score
        # Adjust weights as needed (0.7 / 0.3 is a standard starting point)
        hybrid_score = (similarity * 0.7) + (rank * 0.3)
        
        stmt = select(Chunk).add_columns(hybrid_score.label("score"))
        
        if document_ids:
             stmt = stmt.where(Chunk.document_id.in_(document_ids))
             
        stmt = stmt.order_by(desc(hybrid_score)).limit(top_k)
        
        # Execute and unpack (Chunk, score) tuples
        results = self.db.execute(stmt).all()
        return [row[0] for row in results]
    
    def query(
        self,
        question: str,
        document_ids: List[str] = None,
        top_k: int = 5,
        conversation_history: List = None,
        system_prompt: str = None
    ) -> Dict:
        """Executes full RAG flow with optional conversation context.

        Args:
            question: User's current question
            document_ids: Optional list of document IDs to search
            top_k: Number of similar chunks to retrieve
            conversation_history: List of previous Message objects for context
            system_prompt: Custom system prompt (uses default if None)

        Returns:
            Dict with 'answer', 'sources', and 'context_warning' keys
        """
        # 1. Search relevant chunks
        chunks = self.search_similar_chunks(question, document_ids, top_k)

        # 2. Build RAG context
        context_parts = []
        sources = []

        for chunk in chunks:
            doc = chunk.document
            location = ""

            if chunk.start_time is not None:
                location = f"[{self._format_time(chunk.start_time)} - {self._format_time(chunk.end_time)}]"
            elif chunk.page_number:
                location = f"[Page {chunk.page_number}]"


            # Format metadata if available
            meta_str = ""
            if doc.metadata_:
                 # Filter or format specific keys if needed, or just dump relevant ones
                 # Prioritize title, author, description, date
                 meta_parts = []
                 for key in ['title', 'author', 'description', 'language', 'duration']:
                     if key in doc.metadata_:
                         meta_parts.append(f"{key.capitalize()}: {doc.metadata_[key]}")
                 if meta_parts:
                     meta_str = f"Metadata: [{', '.join(meta_parts)}]\n"

            context_parts.append(f"--- {doc.original_filename} {location} ---\n{meta_str}{chunk.content}")
            sources.append({
                "document": doc.original_filename,
                "document_id": str(doc.id),
                "page_number": chunk.page_number,
                "chunk_id": str(chunk.id),
                "location": location,
                "text": chunk.content,
                "metadata": doc.metadata_
            })

        if not chunks:
             return {
                 "answer": "No relevant documents found for this query.",
                 "sources": [],
                 "context_warning": None
             }

        rag_context = "\n\n".join(context_parts)

        # 3. Build conversation history context (if provided)
        conversation_context = ""
        context_warning = None

        if conversation_history and len(conversation_history) > 0:
            # Format previous messages
            history_lines = []
            for msg in conversation_history:
                role_label = "User" if msg.role == "user" else "Assistant"
                history_lines.append(f"[Previous {role_label}]: {msg.content}")

            conversation_context = "\n".join(history_lines)

            # Check if approaching context limit (warning at 80% capacity)
            if len(conversation_history) >= 8:  # 8 out of 10 default max
                context_warning = f"Conversation history is getting long ({len(conversation_history)} messages). Consider starting a new conversation for better performance."

        # 4. Use custom or default system prompt
        if not system_prompt:
            system_prompt = """You are a helpful assistant that answers questions based ONLY on the provided context.
        If the information is not in the context, say so.
        Always cite the sources using the strict format: [Source: filename] when relevant.
        Provide detailed and comprehensive answers. Use markdown (bold, lists, headers) to structure your response."""

        # 5. Build final user prompt with all context
        user_prompt_parts = []

        if conversation_context:
            user_prompt_parts.append(f"Previous Conversation:\n{conversation_context}\n")

        user_prompt_parts.append(f"Context from Documents:\n{rag_context}\n")
        user_prompt_parts.append(f"Current Question: {question}\n")
        user_prompt_parts.append("Answer in detail and comprehensively.")

        user_prompt = "\n".join(user_prompt_parts)

        # 6. Generate response with LLM
        response = self.llm.chat(
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}]
        )

        return {
            "answer": response,
            "sources": sources,
            "context_warning": context_warning
        }
    
    @staticmethod
    def _format_time(seconds: float) -> str:
        """Convert seconds to MM:SS or HH:MM:SS."""
        if seconds is None: return ""
        hours, remainder = divmod(int(seconds), 3600)
        minutes, secs = divmod(remainder, 60)
        if hours:
            return f"{hours}:{minutes:02d}:{secs:02d}"
        return f"{minutes}:{secs:02d}"
