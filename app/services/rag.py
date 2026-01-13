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
    
    
    def _generate_search_queries(self, question: str, history: List) -> List[str]:
        """Generates optimized search queries based on user question and history."""
        system_prompt = """You are an expert Search Query Generator.
Your task is to generate 1 to 2 optimized web search queries to find the answer to the user's question.
If the request is simple, generate only 1 query.
If complex, generate maximum 2 specific queries.
IMPORTANT: Ignore any context related to 'Mnemos', 'assistant', or internal system names unless explicitly relevant. Focus purely on the user's topic.
Output ONLY the queries, one per line. Do not include numbering or bullets."""
        
        # Build prompt context
        prompt = f"User Question: {question}\n\n"
        if history:
             prompt += "Conversation Context:\n" + "\n".join([f"{m.role}: {m.content}" for m in history[-3:]]) + "\n\n"
        
        prompt += "Generate search queries:"

        try:
            response = self.llm.chat(system=system_prompt, messages=[{"role": "user", "content": prompt}])
            queries = [q.strip() for q in response.split('\n') if q.strip()]
            return queries[:2] # Limit to 2 max
        except Exception as e:
            print(f"Query generation failed: {e}")
            return [question] # Fallback to original question

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
        system_prompt: str = None,
        web_search: bool = False,
        images: List[str] = None
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
        # 1. Search relevant chunks ONLY if documents are selected
        chunks = []
        if document_ids and len(document_ids) > 0:
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
                "start_time": chunk.start_time,
                "end_time": chunk.end_time,
                "chunk_id": str(chunk.id),
                "location": location,
                "text": chunk.content,
                "file_type": doc.file_type,
                "youtube_url": doc.youtube_url,
                "metadata": doc.metadata_
            })

        rag_context = "\n\n".join(context_parts)

        if web_search:
            from app.services.web_search import WebSearchService
            search_service = WebSearchService()
            
            # Agentic Step: Generate optimized queries
            search_queries = self._generate_search_queries(question, conversation_history)
            
            all_web_context = []
            for q in search_queries:
                print(f"Executing Web Search: {q}")
                web_results = search_service.search(q)
                if web_results["context"]:
                    all_web_context.append(f"Query: {q}\n{web_results['context']}")
                    sources.extend(web_results["sources"])
            
            # Append web content
            if all_web_context:
                rag_context += "\n\n=== WEB SEARCH RESULTS ===\n" + "\n\n".join(all_web_context)
                
                # Update system prompt hint if no custom one provided
                if not system_prompt:
                    system_prompt = """You are a helpful assistant. Use the provided Document Context and Web Search Results to answer the user's question.
If the information is not in the context, say so.
Always cite the sources using the format: [Source: filename] or [Web Source: Title].
Provide detailed and comprehensive answers."""

        # Check if we have ANY context (chunks or web)
        if not rag_context:
             # If using vision (images present) OR it's a vanilla chat (no docs requested, no web search), 
             # we allow proceeding without context.
             is_vanilla = (not document_ids) and (not web_search)
             
             if not images and not is_vanilla:
                 return {
                     "answer": "No relevant documents or web results found for this query.",
                     "sources": [],
                     "context_warning": None
                 }
        
        # 3. Build conversation history context (if provided)
        conversation_context = ""
        context_warning = None

        if conversation_history and len(conversation_history) > 0:
            # Format previous messages
            history_lines = []
            for msg in conversation_history:
                role_label = "User" if msg.role == "user" else "Assistant"
                # If message has images, mention it? 
                # (For now we rely on history_msgs being just text here unless we do multimodal history replays, 
                # which is complex. We'll stick to text-only context for history for now to avoid token explosion)
                history_lines.append(f"[Previous {role_label}]: {msg.content}")

            conversation_context = "\n".join(history_lines)

            # Check if approaching context limit (warning at 80% capacity)
            if len(conversation_history) >= 8:  # 8 out of 10 default max
                context_warning = f"Conversation history is getting long ({len(conversation_history)} messages). Consider starting a new conversation for better performance."

        # 4. Use custom or default system prompt
        if not system_prompt:
            if rag_context:
                # RAG Mode default prompt
                system_prompt = """You are a helpful assistant that answers questions based ONLY on the provided context.
If the information is not in the context, say so.
Always cite the sources using the strict format: [Source: filename] when relevant.
Provide detailed and comprehensive answers. Use markdown (bold, lists, headers) to structure your response."""
            else:
                # Vanilla / Vision Mode default prompt
                system_prompt = """You are a helpful assistant. Answer the user's questions to the best of your ability.
Provide detailed and comprehensive answers. Use markdown (bold, lists, headers) to structure your response."""

        # Inject User Memories
        from app.models.user_preferences import UserPreferences
        from app.models.memory import UserMemory
        prefs = self.db.query(UserPreferences).first()
        if prefs and prefs.memory_enabled:
             memories = self.db.query(UserMemory).all()
             if memories:
                 mem_text = "\n".join([f"- {m.content}" for m in memories])
                 system_prompt += f"\n\nUser Profile / Memories:\n{mem_text}"

        # 5. Build final user prompt with all context
        user_prompt_parts = []

        if conversation_context:
            user_prompt_parts.append(f"Previous Conversation:\n{conversation_context}\n")

        if rag_context:
            user_prompt_parts.append(f"Context from Documents and Web:\n{rag_context}\n")
            
        user_prompt_parts.append(f"Current Question: {question}\n")
        user_prompt_parts.append("Answer in detail and comprehensively.")

        user_prompt = "\n".join(user_prompt_parts)

        # 6. Generate response with LLM
        response = self.llm.chat(
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
            images=images
        )

        return {
            "answer": response,
            "sources": sources,
            "context_warning": context_warning,
            "search_queries": search_queries if web_search else []
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
