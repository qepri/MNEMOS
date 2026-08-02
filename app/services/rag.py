from pgvector.sqlalchemy import Vector
from sqlalchemy import select, text, or_
from sqlalchemy.orm import selectinload
from typing import List, Dict, Union
from app.models.chunk import Chunk
from app.models.document import Document
from app.models.section import DocumentSection
from app.models.knowledge_graph import Concept, HyperEdge, HyperEdgeMember
from app.services.embedder import EmbedderService
from app.services.llm_client import get_llm_client, LLMError
import json
import logging

logger = logging.getLogger(__name__)

# Context window sizes keyed by provider/model prefix (safe defaults)
_MODEL_CTX = {
    "gpt-4": 8192,
    "gpt-4o": 128000,
    "gpt-3.5": 16385,
    "claude": 200000,
    "llama": 4096,
    "mistral": 32768,
    "deepseek": 65536,
    "default": 8192,
}


def _count_tokens(text: str, model: str = "") -> int:
    try:
        import tiktoken
        try:
            enc = tiktoken.encoding_for_model(model)
        except Exception:
            enc = tiktoken.get_encoding("cl100k_base")
        return len(enc.encode(text))
    except ImportError:
        # Rough approximation when tiktoken is unavailable
        return len(text) // 4


def _model_ctx_size(model: str) -> int:
    m = (model or "").lower()
    for prefix, size in _MODEL_CTX.items():
        if m.startswith(prefix):
            return size
    return _MODEL_CTX["default"]


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

    
    # Must stay in sync with chunk_ts_config() in the a006 migration and with
    # the lang_map in app/tasks/processing.py. If index-time and query-time
    # configurations disagree, keyword search silently returns nothing.
    _PG_LANG_MAP = {
        'en': 'english', 'es': 'spanish', 'de': 'german', 'fr': 'french',
        'it': 'italian', 'ru': 'russian', 'pt': 'portuguese', 'nl': 'dutch',
        'sv': 'swedish', 'no': 'norwegian', 'da': 'danish', 'fi': 'finnish',
    }

    def _detect_query_language(self, text: str) -> str:
        """Detects language of the query and maps to a Postgres TS config."""
        try:
            from langdetect import detect
            return self._PG_LANG_MAP.get(detect(text), 'english')
        except Exception:
            return 'english'

    def _retrieve_via_graph(self, query: str, document_ids: List[str] = None, top_k: int = 3) -> List[Union[DocumentSection, Chunk]]:
        """
        Retrieves context via Knowledge Graph Traversal.
        Returns real DocumentSection and Chunk objects (no fake wrappers).
        """
        from sqlalchemy import desc

        query_embedding = self.embedder.embed_query(query)

        stmt = select(Concept).order_by(
            Concept.embedding.cosine_distance(query_embedding)
        ).limit(top_k)
        concepts = self.db.execute(stmt).scalars().all()

        if not concepts:
            return []

        logger.info(f"[GraphRAG] Found concepts: {[c.name for c in concepts]}")

        stmt = (
            select(HyperEdgeMember, HyperEdge, DocumentSection, Chunk)
            .join(HyperEdge, HyperEdge.id == HyperEdgeMember.hyper_edge_id)
            .outerjoin(DocumentSection, DocumentSection.id == HyperEdge.source_section_id)
            .outerjoin(Chunk, Chunk.id == HyperEdge.source_chunk_id)
            .where(HyperEdgeMember.concept_id.in_([c.id for c in concepts]))
            .limit(5 * len(concepts))
        )
        if document_ids:
            stmt = stmt.where(HyperEdge.source_document_id.in_(document_ids))

        rows = self.db.execute(stmt).all()

        results: List[Union[DocumentSection, Chunk]] = []
        seen_ids = set()
        for _mem, _edge, section, chunk in rows:
            if section is not None and section.id is not None and section.id not in seen_ids:
                seen_ids.add(section.id)
                results.append(section)
            elif chunk is not None and chunk.id is not None and chunk.id not in seen_ids:
                seen_ids.add(chunk.id)
                results.append(chunk)

        return results

    def _mmr(self, query_emb: List[float], candidates: List[Chunk], k: int, lam: float = 0.7) -> List[Chunk]:
        """Maximal Marginal Relevance re-ranking for diversity. λ=0.7 balances relevance vs diversity."""
        import numpy as np
        def cos(a, b):
            a, b = np.array(a), np.array(b)
            return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-9))

        selected, remaining = [], list(candidates)
        while remaining and len(selected) < k:
            best, best_score = None, -1e9
            for c in remaining:
                rel = cos(query_emb, c.embedding)
                div = max((cos(c.embedding, s.embedding) for s in selected), default=0)
                score = lam * rel - (1 - lam) * div
                if score > best_score:
                    best, best_score = c, score
            selected.append(best)
            remaining.remove(best)
        return selected

    def search_similar_chunks(
        self,
        query: str,
        document_ids: List[str] = None,
        top_k: int = 10
    ) -> List[Chunk]:
        """
        Hybrid retrieval via Reciprocal Rank Fusion (RRF) with score floor,
        MMR diversity re-ranking, and neighbor-window expansion.
        """
        from sqlalchemy import func, desc

        query_embedding = self.embedder.embed_query(query)
        pg_lang = self._detect_query_language(query)

        base_filter = None
        if document_ids:
            from uuid import UUID
            uuid_list = [UUID(doc_id) if isinstance(doc_id, str) else doc_id for doc_id in document_ids]
            base_filter = Chunk.document_id.in_(uuid_list)

        eager = selectinload(Chunk.document).selectinload(Document.sections)

        # --- Pass 1: Vector search ---
        similarity = 1 - Chunk.embedding.cosine_distance(query_embedding)
        stmt_vec = select(Chunk).options(eager)
        if base_filter is not None:
            stmt_vec = stmt_vec.where(base_filter)
        stmt_vec = stmt_vec.order_by(desc(similarity)).limit(top_k)
        vec_results = self.db.execute(stmt_vec).scalars().all()

        # --- Pass 2: Keyword search ---
        kw_query = func.plainto_tsquery(pg_lang, query)
        rank = func.ts_rank_cd(Chunk.search_vector, kw_query)
        stmt_kw = select(Chunk).options(eager).add_columns(rank.label("kw_score"))
        if base_filter is not None:
            stmt_kw = stmt_kw.where(base_filter)
        stmt_kw = stmt_kw.where(Chunk.search_vector.op("@@")(kw_query))
        stmt_kw = stmt_kw.order_by(desc(rank)).limit(top_k)
        kw_results = self.db.execute(stmt_kw).all()
        kw_chunks = [row[0] for row in kw_results]

        logger.info(f"[Retrieval] Vector hits: {len(vec_results)}, Keyword hits: {len(kw_chunks)}")

        # --- RRF Merge (k=60 is the standard constant) ---
        RRF_K = 60
        scores: Dict[str, float] = {}
        chunk_map: Dict[str, Chunk] = {}

        for rank_pos, chunk in enumerate(vec_results):
            cid = str(chunk.id)
            scores[cid] = scores.get(cid, 0.0) + 1.0 / (RRF_K + rank_pos + 1)
            chunk_map[cid] = chunk

        for rank_pos, chunk in enumerate(kw_chunks):
            cid = str(chunk.id)
            scores[cid] = scores.get(cid, 0.0) + 1.0 / (RRF_K + rank_pos + 1)
            chunk_map[cid] = chunk

        sorted_ids = sorted(scores, key=lambda cid: scores[cid], reverse=True)

        # --- 2.5.3: RRF score floor (before MMR/neighbors) ---
        if scores:
            top_score = max(scores.values())
            sorted_ids = [cid for cid in sorted_ids if scores[cid] >= max(0.01, top_score * 0.5)]
        sorted_ids = sorted_ids[:top_k]

        selected = [chunk_map[cid] for cid in sorted_ids]

        # --- 2.5.2: MMR diversity re-rank ---
        if len(selected) > 1:
            selected = self._mmr(query_embedding, selected, k=len(selected))

        # --- 2.5.1: Neighbor-window expansion ---
        if selected:
            pairs = set()
            for c in selected:
                for delta in (-1, 1):
                    pairs.add((c.document_id, c.chunk_index + delta))
            if pairs:
                conds = [(Chunk.document_id == d) & (Chunk.chunk_index == i) for d, i in pairs]
                neighbors = self.db.execute(
                    select(Chunk).options(eager).where(or_(*conds))
                ).scalars().all()
                seen = {c.id for c in selected}
                for n in neighbors:
                    if n.id not in seen:
                        n._is_context_neighbor = True
                        selected.append(n)

        return selected
    
    def query(
        self,
        question: str,
        document_ids: List[str] = None,
        top_k: int = 10,
        conversation_history: List = None,
        system_prompt: str = None,
        web_search: bool = False,
        use_graph_rag: bool = False,
        images: List[str] = None
    ) -> Dict:
        """Executes full RAG flow with optional conversation context."""
        import time

        search_queries = []
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

        # Token budget guard: trim lowest-ranked chunks if prompt overflows model context
        try:
            _llm_prefs = self.db.query(UserPreferences).first()
            reserve_tokens = _llm_prefs.llm_max_tokens if _llm_prefs else 4096
        except Exception:
            reserve_tokens = 4096
        model_name = self.llm.model or ""
        ctx_size = _model_ctx_size(model_name)
        sys_tokens = _count_tokens(system_prompt, model_name)
        prompt_tokens = _count_tokens(user_prompt, model_name)
        budget = ctx_size - reserve_tokens - sys_tokens
        if prompt_tokens > budget and chunks:
            dropped = 0
            # Drop chunks from lowest rank upward until under budget
            while chunks and prompt_tokens > budget:
                chunks.pop()
                dropped += 1
                rag_context, sources = self._build_hierarchical_context(chunks, graph_sections)
                user_prompt_parts_new = []
                if conversation_context:
                    user_prompt_parts_new.append(f"Previous Conversation:\n{conversation_context}\n")
                if rag_context:
                    user_prompt_parts_new.append(f"Context from Documents and Web:\n{rag_context}\n")
                user_prompt_parts_new.append(f"Current Question: {question}\n")
                user_prompt_parts_new.append("Answer in detail and comprehensively.")
                user_prompt = "\n".join(user_prompt_parts_new)
                prompt_tokens = _count_tokens(user_prompt, model_name)
            logger.info(f"[Context] Dropped {dropped} chunks to fit token budget ({budget} tokens)")

        # Log Context Stats
        ctx_len = len(rag_context) if rag_context else 0
        hist_len = len(conversation_context) if conversation_context else 0
        logger.info(f"[Context] Docs/Web: {ctx_len} chars | History: {hist_len} chars | Prompt Total: {len(user_prompt)} chars")

        logger.debug("--- FINAL LLM PROMPT ---")
        logger.debug(user_prompt)
        logger.debug("------------------------")

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


    def _build_hierarchical_context(self, chunks: List[Chunk], graph_results: List[Union[DocumentSection, Chunk]]):
        """
        Groups content by Document -> Section -> Chunks to save tokens and provide structure.
        Accepts real DocumentSection and Chunk objects from graph retrieval (no fake wrappers).
        Returns: (formatted_context_string, sources_list)
        """
        docs_map = {}
        sources = []

        # 1. Process Graph Results (DocumentSection or Chunk)
        for item in graph_results:
            if not item.document_id:
                continue

            d_id = str(item.document_id)
            if d_id not in docs_map:
                if isinstance(item, DocumentSection):
                    doc = item.document if item.document else self.db.query(Document).get(item.document_id)
                else:
                    doc = item.document if item.document else self.db.query(Document).get(item.document_id)
                docs_map[d_id] = {'obj': doc, 'sections': {}, 'orphans': []}

            if isinstance(item, DocumentSection):
                s_id = str(item.id)
                if s_id not in docs_map[d_id]['sections']:
                    docs_map[d_id]['sections'][s_id] = {'obj': item, 'chunks': [], 'is_graph': True}
                doc = docs_map[d_id]['obj']
                sources.append({
                    "document": doc.original_filename if doc else "Unknown Document",
                    "document_id": str(doc.id) if doc else None,
                    "location": f"Graph Cluster: {item.title}",
                    "text": (item.content or "")[:200] + "...",
                    "type": "graph_node"
                })
            else:
                # Chunk from graph — add as orphan tagged graph_chunk
                docs_map[d_id]['orphans'].append(item)
                doc = docs_map[d_id]['obj']
                sources.append({
                    "document": doc.original_filename if doc else "Unknown Document",
                    "document_id": str(doc.id) if doc else None,
                    "chunk_id": str(item.id),
                    "location": f"[Page {item.page_number}]" if item.page_number else "",
                    "text": item.content[:200] + "...",
                    "type": "graph_chunk"
                })


        # 2. Process Standard Chunks (document + sections already eager-loaded)
        for d_id, doc in {c.document_id: c.document for c in chunks}.items():
            if str(d_id) not in docs_map:
                docs_map[str(d_id)] = {'obj': doc, 'sections': {}, 'orphans': []}

        for chunk in chunks:
            d_id = str(chunk.document_id)
            doc_data = docs_map[d_id]
            is_neighbor = getattr(chunk, '_is_context_neighbor', False)

            found = False
            if chunk.page_number:
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

            location = f"[Page {chunk.page_number}]" if chunk.page_number else ""
            sources.append({
                "document": chunk.document.original_filename,
                "document_id": str(chunk.document.id),
                "chunk_id": str(chunk.id),
                "location": location,
                "text": chunk.content,
                "type": "context" if is_neighbor else "chunk",
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

    def stream_query(
        self,
        question: str,
        document_ids: List[str] = None,
        top_k: int = 10,
        conversation_history: List = None,
        system_prompt: str = None,
        web_search: bool = False,
        use_graph_rag: bool = False,
    ):
        """
        Generator that performs retrieval then streams LLM tokens.
        Yields dicts:
          {"type": "metadata", "sources": [...], "search_queries": [...]}
          {"type": "token", "delta": "..."}
          {"type": "done", "answer": "<full accumulated text>"}
        """
        import time

        search_queries = []
        chunks = []
        if document_ids:
            chunks = self.search_similar_chunks(question, document_ids, top_k)

        graph_sections = []
        if use_graph_rag:
            graph_sections = self._retrieve_via_graph(question, document_ids=document_ids, top_k=3)

        rag_context, sources = self._build_hierarchical_context(chunks, graph_sections)

        if web_search:
            from app.services.web_search import WebSearchService
            search_service = WebSearchService()
            search_queries = self._generate_search_queries(question, conversation_history)
            all_web_context = []
            for q in search_queries:
                web_results = search_service.search(q)
                if web_results["context"]:
                    all_web_context.append(f"Query: {q}\n{web_results['context']}")
                    sources.extend(web_results["sources"])
            if all_web_context:
                rag_context += "\n\n=== WEB SEARCH RESULTS ===\n" + "\n\n".join(all_web_context)

        yield {"type": "metadata", "sources": sources, "search_queries": search_queries}

        conversation_context = ""
        if conversation_history:
            history_lines = []
            for msg in conversation_history:
                role_label = "User" if msg.role == "user" else "Assistant"
                history_lines.append(f"[Previous {role_label}]: {msg.content}")
            conversation_context = "\n".join(history_lines)

        if not system_prompt:
            if rag_context:
                system_prompt = """You are a helpful assistant that answers questions based ONLY on the provided context.
If the information is not in the context, say so.
Always cite the sources using the strict format: [Source: filename] when relevant.
Provide detailed and comprehensive answers. Use markdown (bold, lists, headers) to structure your response."""
            else:
                system_prompt = """You are a helpful assistant. Answer the user's questions to the best of your ability.
Provide detailed and comprehensive answers. Use markdown (bold, lists, headers) to structure your response."""

        from app.models.user_preferences import UserPreferences
        from app.models.memory import UserMemory
        prefs = self.db.query(UserPreferences).first()
        if prefs and prefs.memory_enabled:
            memories = self.db.query(UserMemory).all()
            if memories:
                mem_text = "\n".join([f"- {m.content}" for m in memories])
                system_prompt += f"\n\nUser Profile / Memories:\n{mem_text}"

        user_prompt_parts = []
        if conversation_context:
            user_prompt_parts.append(f"Previous Conversation:\n{conversation_context}\n")
        if rag_context:
            user_prompt_parts.append(f"Context from Documents and Web:\n{rag_context}\n")
        user_prompt_parts.append(f"Current Question: {question}\n")
        user_prompt_parts.append("Answer in detail and comprehensively.")
        user_prompt = "\n".join(user_prompt_parts)

        accumulated = ""
        for token in self.llm.stream_chat(system=system_prompt, messages=[{"role": "user", "content": user_prompt}]):
            accumulated += token
            yield {"type": "token", "delta": token}

        yield {"type": "done", "answer": accumulated}
