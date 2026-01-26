from pgvector.sqlalchemy import Vector
from sqlalchemy import select, text
from typing import List, Dict
from app.models.chunk import Chunk
from app.models.document import Document
from app.models.section import DocumentSection
from app.models.knowledge_graph import Concept, HyperEdge, HyperEdgeMember
from app.services.embedder import EmbedderService
from app.services.llm_client import get_llm_client

from app.services.embedder import EmbedderService
from app.services.llm_client import get_llm_client
import json

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

    
    def _detect_query_language(self, text: str) -> str:
        """Detects language of the query and maps to Postgres config."""
        try:
            from langdetect import detect
            code = detect(text)
            lang_map = {
                'en': 'english', 'es': 'spanish', 'de': 'german', 'fr': 'french',
                'it': 'italian', 'ru': 'russian', 'pt': 'portuguese', 'nl': 'dutch'
            }
            return lang_map.get(code, 'english')
        except:
            return 'english'

    def search_similar_documents(self, query: str, top_k: int = 3) -> List[Document]:
        """
        Search for documents based on Summary Similarity (Hybrid).
        """
        from sqlalchemy import func, desc
        
        # 1. Embed Query
        query_embedding = self.embedder.embed(query)
        
        # 2. Detect Language for Search
        pg_lang = self._detect_query_language(query)
        
        # 3. Hybrid Search on Summary
        # Similarity
        similarity = 1 - Document.summary_embedding.cosine_distance(query_embedding)
        
        # Keyword (TS Rank) using dynamic language
        kw_query = func.websearch_to_tsquery(pg_lang, query)
        rank = func.ts_rank_cd(Document.summary_search_vector, kw_query)
        
        hybrid_score = (similarity * 0.8) + (rank * 0.2) # Summaries are semantic-heavy
        
        stmt = select(Document).add_columns(hybrid_score.label("score"))
        stmt = stmt.order_by(desc(hybrid_score)).limit(top_k)
        
        results = self.db.execute(stmt).all()
        return [row[0] for row in results]

    
    def _retrieve_via_graph(self, query: str, document_ids: List[str] = None, top_k: int = 3) -> List[DocumentSection]:
        """
        Retrieves context via Knowledge Graph Traversal:
        Query -> [Vector Search] -> Similar Concepts -> [HyperEdge] -> Linked Sections
        """
        from sqlalchemy import select, desc
        
        # 1. Embed Query
        query_embedding = self.embedder.embed(query)
        
        # 2. Find Similar Concepts
        # We find concepts that are semantically close to the query
        stmt = select(Concept).order_by(
            Concept.embedding.cosine_distance(query_embedding)
        ).limit(top_k)
        
        concepts = self.db.execute(stmt).scalars().all()
        
        if not concepts:
            return []
            
        print(f"[GraphRAG] Found concepts: {[c.name for c in concepts]}")
        
        # 3. Traverse to Sections
        # Concept -> HyperEdgeMember -> HyperEdge -> Section
        
        relevant_sections = []
        for concept in concepts:
            # Verify if this concept is actually relevant (distance check could be added here)
            
            # Find edges containing this concept
            # We want edges where this concept is a member
            # Optimization: Could be done in one join query
            members = self.db.query(HyperEdgeMember).filter_by(concept_id=concept.id).limit(5).all()
            
            for mem in members:
                edge = self.db.query(HyperEdge).get(mem.hyper_edge_id)
                if not edge: continue

                # Filter by Document ID if provided
                if document_ids:
                    # Check if edge has a source_document_id and if it's in the allowed list
                    if not edge.source_document_id or str(edge.source_document_id) not in document_ids:
                         continue

                # Case A: Linked to Section (Graph Unifier)
                if edge.source_section_id:
                     section = self.db.query(DocumentSection).get(edge.source_section_id)
                     if section:
                         relevant_sections.append(section)
                
                # Case B: Linked to Chunk (Hypergraph Extractor)
                elif edge.source_chunk_id:
                     chunk = self.db.query(Chunk).get(edge.source_chunk_id)
                     if chunk:
                         # Create a pseudo-section or wrapper for consistency
                         # We'll re-use DocumentSection model on the fly or adjust return type?
                         # Simpler: Just wrap it in a lightweight object or existing Section model with null ID?
                         # Or better: Just append to a list of "ContentNodes" and adjust return type to List[Any]
                         
                         # Hack: Use DocumentSection as a container for now
                         # Ideally we refactor return type, but to be KISS:
                         fake_section = DocumentSection(
                             id=None, # Indicating it's dynamic
                             title=f"Chunk from {chunk.document.original_filename} (Graph)", 
                             content=chunk.content,
                             document_id=chunk.document_id
                         )
                         relevant_sections.append(fake_section)
        
        # Deduplicate by Content (since IDs might be None for chunks)
        unique_content = {}
        for s in relevant_sections:
            if s.content not in unique_content:
                unique_content[s.content] = s
            
        return list(unique_content.values())

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
        pg_lang = self._detect_query_language(query)
        
        # 1. Similarity Score (1 - Distance)
        # Cosine distance is usually 0 (same) to 2 (opposite).
        # We want similarity: 1.0 is match, 0.0 is orthogonal/opposite.
        similarity = 1 - Chunk.embedding.cosine_distance(query_embedding)
        
        # 2. Keyword Score (TS Rank)
        # websearch_to_tsquery handles natural language better than plain to_tsquery
        kw_query = func.websearch_to_tsquery(pg_lang, query)
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
        use_graph_rag: bool = False,
        images: List[str] = None
    ) -> Dict:
        """Executes full RAG flow with optional conversation context."""
        import time
        import logging
        
        # Setup basic logging
        logging.basicConfig(level=logging.INFO)
        logger = logging.getLogger(__name__)

        start_time = time.time()
        logger.info(f"--- START RAG QUERY: '{question}' ---")

        # 1. Search relevant chunks (Standard Retrieval)
        chunks = []
        t0 = time.time()
        
        # Standard Hybrid Search
        if document_ids and len(document_ids) > 0:
            chunks = self.search_similar_chunks(question, document_ids, top_k)
            logger.info(f"[Retrieval] Found {len(chunks)} chunks in {time.time() - t0:.2f}s")
        
        # 2. Graph retrieval (Optional)
        graph_sections = []
        if use_graph_rag:
            t_graph = time.time()
            logger.info("[Retrieval] Executing Graph-RAG...")
            graph_sections = self._retrieve_via_graph(question, document_ids=document_ids, top_k=3)
            logger.info(f"[Retrieval] Graph found {len(graph_sections)} sections in {time.time() - t_graph:.2f}s")
            
        if not chunks and not graph_sections:
            logger.info("[Retrieval] Skipped (No docs selected and no graph results)")

        # 3. Build RAG context
        # We now use a hierarchical structure: Document -> Section (Chapter) -> Chunk
        rag_context, sources = self._build_hierarchical_context(chunks, graph_sections)

        if web_search:
            from app.services.web_search import WebSearchService
            search_service = WebSearchService()
            
            t_web = time.time()
            logger.info("[Web] Generating search queries...")
            
            # Agentic Step: Generate optimized queries
            # Agentic Step: Generate optimized queries
            search_queries = self._generate_search_queries(question, conversation_history)
            logger.info(f"[Web] Generated queries:\n{json.dumps(search_queries, indent=2)}")
            
            all_web_context = []
            for q in search_queries:
                logger.info(f"[Web] Executing Search: {q}")
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
            
            logger.info(f"[Web] Finished in {time.time() - t_web:.2f}s. Sources: {len(all_web_context)}")

        # Check if we have ANY context (chunks or web)
        if not rag_context:
             # If using vision (images present) OR it's a vanilla chat (no docs requested, no web search), 
             # we allow proceeding without context.
             is_vanilla = (not document_ids) and (not web_search)
             
             if not images and not is_vanilla:
                 logger.warning("[RAG] No context found and not in vanilla mode. Aborting.")
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
                 logger.info(f"[Memory] Injected {len(memories)} user memories.")

        # 5. Build final user prompt with all context
        user_prompt_parts = []

        if conversation_context:
            user_prompt_parts.append(f"Previous Conversation:\n{conversation_context}\n")

        if rag_context:
            user_prompt_parts.append(f"Context from Documents and Web:\n{rag_context}\n")
            
        user_prompt_parts.append(f"Current Question: {question}\n")
        user_prompt_parts.append("Answer in detail and comprehensively.")

        user_prompt = "\n".join(user_prompt_parts)

        # Log Context Stats
        ctx_len = len(rag_context) if rag_context else 0
        hist_len = len(conversation_context) if conversation_context else 0
        logger.info(f"[Context] Docs/Web: {ctx_len} chars | History: {hist_len} chars | Prompt Total: {len(user_prompt)} chars")

        # --- LOGGING: Final Prompt ---
        logger.info("--- FINAL LLM PROMPT ---")
        logger.info(user_prompt)
        logger.info("------------------------")

        # 6. Generate response with LLM
        logger.info("[LLM] Sending request to model...")
        t_llm = time.time()
        
        response = self.llm.chat(
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
            images=images
        )
        
        elapsed_llm = time.time() - t_llm
        total_time = time.time() - start_time
        logger.info(f"[LLM] Response received in {elapsed_llm:.2f}s.")
        logger.info(f"--- FINISHED RAG QUERY in {total_time:.2f}s ---")

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


    def _build_hierarchical_context(self, chunks: List[Chunk], graph_sections: List[DocumentSection]):
        """
        Groups content by Document -> Section -> Chunks to save tokens and provide structure.
        Returns: (formatted_context_string, sources_list)
        """
        from collections import defaultdict
        
        # Data Structure:
        # docs[doc_id] = { 'obj': Document, 'sections': { sec_id: {'obj': Section, 'chunks': []} }, 'orphans': [] }
        docs_map = {} 
        sources = []

        # 1. Process Graph Sections (High Level Concepts)
        for section in graph_sections:
            if not section.document_id: continue # Skip if no doc link (rare)
            
            d_id = str(section.document_id)
            if d_id not in docs_map:
                # We need the document object. 
                # Optimization: It's likely loaded on section.document, or we fetch it.
                if section.document:
                    doc = section.document
                else:
                    # Fallback lookup
                    doc = self.db.query(Document).get(section.document_id)
                docs_map[d_id] = {'obj': doc, 'sections': {}, 'orphans': []}
            
            s_id = str(section.id) if section.id else "virtual_graph_section"
            if s_id not in docs_map[d_id]['sections']:
                 docs_map[d_id]['sections'][s_id] = {'obj': section, 'chunks': [], 'is_graph': True}
            
            # Graph sections are their own content, often without sub-chunks in this specific flow.
            # We treat the section content itself as the "chunk".
            # If it's a "fake_section" from a chunk (see _retrieve_via_graph), it has content.
            
            sources.append({
                "document": doc.original_filename if doc else "Unknown Document",
                "document_id": str(doc.id) if doc else None,
                "location": f"Graph Cluster: {section.title}",
                "text": section.content[:200] + "...",
                "type": "graph_node"
            })


        # 2. Process Standard Chunks
        # We need to map chunks to sections.
        # Efficient way: For each doc, fetch its sections once, then map chunks.
        
        # First, ensure all docs are in map
        chunk_docs = {c.document_id: c.document for c in chunks}
        for d_id, doc in chunk_docs.items():
            if str(d_id) not in docs_map:
                docs_map[str(d_id)] = {'obj': doc, 'sections': {}, 'orphans': []}

        # Pre-fetch sections for these docs to allow mapping
        # We can utilize the relationship doc.sections if available, or query.
        # Assuming eager load or reasonable lazy load for now.
        
        for chunk in chunks:
            d_id = str(chunk.document_id)
            doc_data = docs_map[d_id]
            
            # Find which section this chunk belongs to
            parent_section = None
            
            # Iterate through existing sections in our map FIRST (maybe graph brought them in)
            # Then check other sections of the doc.
            # To be efficient: just check the doc's section list.
            
            found = False
            if chunk.page_number:
                # Naive search in doc's sections
                # In prod: use interval tree or optimized query. Here: loop is fine for standard doc retrieval (5 docs)
                for sec in doc_data['obj'].sections:
                    if sec.start_page and sec.end_page and sec.start_page <= chunk.page_number <= sec.end_page:
                        s_id = str(sec.id)
                        if s_id not in doc_data['sections']:
                            doc_data['sections'][s_id] = {'obj': sec, 'chunks': [], 'is_graph': False}
                        
                        doc_data['sections'][s_id]['chunks'].append(chunk)
                        found = True
                        break
            
            if not found:
                doc_data['orphans'].append(chunk)

            # Add to sources
            location = f"[Page {chunk.page_number}]" if chunk.page_number else ""
            sources.append({
                "document": chunk.document.original_filename,
                "document_id": str(chunk.document.id),
                "chunk_id": str(chunk.id),
                "location": location,
                "text": chunk.content,
                "type": "chunk",
                "metadata": chunk.document.metadata_
            })
            
        # 3. Build String
        context_lines = []
        
        for d_id, data in docs_map.items():
            doc = data['obj']
            # Header
            context_lines.append(f"=== Document: {doc.original_filename} ===")
            
            # Metadata
            meta = []
            if doc.metadata_:
                if 'author' in doc.metadata_: meta.append(f"Author: {doc.metadata_['author']}")
                if 'language' in doc.metadata_: meta.append(f"Lang: {doc.metadata_['language']}")
            if doc.summary:
                # Truncate summary to avoid token bloat
                clean_summ = doc.summary.replace("\n", " ")[:300]
                meta.append(f"Summary: {clean_summ}...")
            
            if meta:
                context_lines.append(" | ".join(meta))
            context_lines.append("") # Spacer
            
            # Sections
            for s_id, s_data in data['sections'].items():
                section = s_data['obj']
                is_graph = s_data.get('is_graph', False)
                
                heading = f"### Chapter: {section.title}"
                if is_graph: heading += " (Graph Linked)"
                context_lines.append(heading)
                
                # If the section itself came from graph, it might have content directly
                if is_graph and section.content:
                     # This is a graph node content (concept or chunk wrapper)
                     context_lines.append(f"{section.content}\n")
                
                # Chunks within this section
                # Remove duplicates if graph content is same as chunk?
                # For now, just print chunks.
                for chunk in s_data['chunks']:
                     loc = f"[Page {chunk.page_number}]" if chunk.page_number else ""
                     context_lines.append(f"- {loc}: {chunk.content}\n")
                
            # Orphans (Chunks not in any section or generic)
            if data['orphans']:
                if data['sections']: # Only print header if we successfully categorized others
                    context_lines.append("### Uncategorized Fragments")
                
                for chunk in data['orphans']:
                    loc = f"[Page {chunk.page_number}]" if chunk.page_number else ""
                    context_lines.append(f"- {loc}: {chunk.content}\n")
            
            context_lines.append("\n") # separator between docs

        return "\n".join(context_lines), sources
