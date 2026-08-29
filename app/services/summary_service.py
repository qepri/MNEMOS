from app.extensions import db
from app.models.document import Document
from app.models.chunk import Chunk
from app.models.knowledge_graph import Concept
from app.services.llm_client import get_llm_client, reset_client
from app.services.embedder import EmbedderService
import logging
from uuid import UUID
import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed

logger = logging.getLogger(__name__)

class SummaryService:
    @staticmethod
    def _sanitize_title(title: str, max_length: int = 250) -> str:
        """
        Sanitize and truncate section title intelligently.

        Truncates at word boundaries when possible to maintain readability.
        Leaves 5-char buffer from database limit (255) for safety.

        Args:
            title: Raw title from LLM
            max_length: Maximum allowed length (default 250)

        Returns:
            Sanitized title that fits within database constraints
        """
        if not title:
            return 'Untitled Section'

        # Strip whitespace
        title = title.strip()

        # If within limit, return as-is
        if len(title) <= max_length:
            return title

        # Log warning for monitoring
        logger.warning(f"Title exceeds {max_length} chars (actual: {len(title)}), truncating")

        # Truncate at word boundary
        truncated = title[:max_length - 3]  # Leave room for ellipsis
        last_space = truncated.rfind(' ')

        if last_space > max_length * 0.8:  # Only use word boundary if it's not too far back
            truncated = truncated[:last_space]

        return truncated + '...'

    @staticmethod
    def generate_summary(document_id: str):
        """
        Generates a summary using Parallel Map-Reduce pattern.
        1. Map (Parallel): Batch chunks -> Section Summary + Structure + Rich Concepts
        2. Reduce: Smart Stitching -> Global Summary + Merged Sections
        """
        try:
            logger.info(f"Generating summary (Parallel Map-Reduce) for doc {document_id}")
            
            # 1. Setup
            oid = UUID(document_id) if isinstance(document_id, str) else document_id
            doc = db.session.get(Document, oid)
            if not doc:
                logger.error(f"Document {document_id} not found")
                return None

            # 2. Fetch ALL chunks (ordered)
            chunks = db.session.query(Chunk).filter_by(document_id=doc.id).order_by(Chunk.chunk_index).all()
            if not chunks:
                logger.warning("No chunks found")
                return None

            reset_client()
            # Note: Each thread will technically use the same client instance if it's singleton, 
            # or we might need one per thread if not thread-safe. Assuming LLMClient is thread-safe or stateless.

            # 3. MAP PHASE: Parallel Batch Processing
            BATCH_SIZE = 5 
            batches = []
            for i in range(0, len(chunks), BATCH_SIZE):
                batch_chunks = chunks[i : i + BATCH_SIZE]
                batches.append((i // BATCH_SIZE, batch_chunks))

            logger.info(f"Starting Parallel Map Phase for {len(chunks)} chunks ({len(batches)} batches)...")
            
            # Initialize Client & Model ONCE in the main thread (with App Context)
            llm_client = get_llm_client()
            
            # Pre-fetch the active model to avoid DB lookup in threads
            from app.services.model_manager import model_manager
            active_model = model_manager.get_model()
            
            map_results = [None] * len(batches) # Pre-allocate to maintain order
            
            with ThreadPoolExecutor(max_workers=5) as executor:
                # Submit all tasks, passing the client AND model explicitly
                future_to_index = {
                    executor.submit(
                        SummaryService._map_process_batch, 
                        batch_chunks, 
                        idx, 
                        llm_client,
                        active_model
                    ): idx 
                    for idx, batch_chunks in batches
                }
                
                for future in as_completed(future_to_index):
                    idx = future_to_index[future]
                    try:
                        result = future.result()
                        map_results[idx] = result
                    except Exception as exc:
                        logger.error(f"Batch {idx} generated an exception: {exc}")

            # Filter out failures
            map_results = [r for r in map_results if r is not None]

            # 4. REDUCE PHASE: Smart Stitching & Aggregation
            logger.info("Starting Smart Reduce Phase...")
            global_summary, merged_sections, global_concepts = SummaryService._reduce_results(map_results)

            # 5. Save to Document
            doc.summary = global_summary
            if doc.metadata_ is None: doc.metadata_ = {}
            doc.metadata_['key_concepts'] = global_concepts

            # 5b. Upsert summary concepts into Concept table so wiki works
            # without requiring the expensive hypergraph pass. Hypergraph
            # (if run later) will enrich these with definitions + relations.
            if global_concepts:
                embedder = EmbedderService()
                for name in global_concepts:
                    norm = name.lower().strip()
                    if not norm:
                        continue
                    existing = db.session.query(Concept).filter_by(name=norm).first()
                    if existing:
                        continue
                    concept = Concept(name=norm)
                    concept.embedding = embedder.embed([norm])[0]
                    db.session.add(concept)

            # 6. Save Sections to 'document_sections' Table
            from app.models.section import DocumentSection
            
            # Clear old sections
            db.session.query(DocumentSection).filter_by(document_id=doc.id).delete()
            
            logger.info(f"Saving {len(merged_sections)} smart sections...")

            for section_data in merged_sections:
                title = SummaryService._sanitize_title(section_data.get('title', 'Untitled Section'))
                content = section_data.get('summary', '')
                if not content: content = f"Section: {title}"

                meta = section_data.get('metadata', {})

                section = DocumentSection(
                    document_id=doc.id,
                    title=title,
                    content=content,
                    start_page=section_data.get('start_page'),
                    end_page=section_data.get('end_page'),
                    metadata_=meta
                )
                db.session.add(section)

            doc.processing_progress = 90
            db.session.commit()
            
            logger.info("Summary generation complete.")
            return global_summary

        except Exception as e:
            logger.error(f"Failed to generate summary: {e}")
            raise e

    @staticmethod
    def _batch_text(chunk_list: list) -> str:
        """
        Continuous text for one MAP batch, with page markers and no repeated seams.

        Chunks overlap by CHUNK_OVERLAP characters. Joining them verbatim feeds
        the model the same sentence twice at every boundary, and since the prompt
        truncates at 3500 characters, those repeats push real content out of the
        window instead of merely costing tokens.

        The page marker is emitted when the page changes rather than once per
        chunk: it is there so the model can fill page_start/page_end, and one
        marker per page says the same thing with less noise.
        """
        from app.services.chunker import ChunkerService

        parts, merged, last_page = [], "", None
        for chunk in chunk_list:
            content = chunk.content or ""
            if not content:
                continue
            content = ChunkerService.strip_overlap(merged, content) if merged else content
            if not content:
                continue
            merged = f"{merged}{content}" if merged else content

            page = chunk.page_number or "?"
            if page != last_page:
                parts.append(f"[Page {page}]")
                last_page = page
            parts.append(content)

        return "\n".join(parts)

    @staticmethod
    def _map_process_batch(chunk_list: list, batch_index: int, llm_client, model_name=None):
        """
        MAP STEP: Summarize batch and Extract Rich Metadata.
        """
        try:
            # llm = get_llm_client() # No longer needed, passed in
            text_block = SummaryService._batch_text(chunk_list)
            
            # Smart Prompt: Infer title, extracting concepts with location awareness
            prompt = f"""Analyze this document segment.
Return a valid JSON object (no markdown):
{{
    "title": "A concise, descriptive title for this segment. MUST be under 80 characters. Infer if missing.",
    "summary": "Concise summary of this segment.",
    "concepts": [
         {{ "name": "Concept Name", "relevance": 1-10 }}
    ],
    "page_start": {chunk_list[0].page_number or 0},
    "page_end": {chunk_list[-1].page_number or 0}
}}

Text:
{text_block[:3500]}
""" 
            response = llm_client.chat(
                system="You are a structured data extractor. Output valid JSON only.",
                messages=[{"role": "user", "content": prompt}],
                model=model_name # Explicitly pass the model to avoid DB lookup
            )
            
            # Parsing logic
            clean_json = response.strip()
            if clean_json.startswith("```json"): clean_json = clean_json[7:]
            if clean_json.endswith("```"): clean_json = clean_json[:-3]
            
            data = json.loads(clean_json)
            return data
            
        except Exception as e:
            logger.warning(f"Map step failed for batch {batch_index}: {e}")
            return None

    @staticmethod
    def _reduce_results(map_results):
        """
        REDUCE STEP: 
        1. Stitch consecutive batches if they share the same topic/title (simple heuristic).
        2. Aggregate concepts.
        3. Generate Global Summary.
        """
        llm = get_llm_client()
        
        # --- A. Smart Stitching (Merging Sections) ---
        merged_sections = []
        if map_results:
            current_section = map_results[0]
            current_section['metadata'] = { 
                "concepts": current_section.get('concepts', []),
                "source_batches": [0]
            }
            
            for i in range(1, len(map_results)):
                next_batch = map_results[i]
                
                # Heuristic: If titles are very similar or just generic "Untitled", merge?
                # For now, we will just keep them separate to ensure granularity, 
                # UNLESS we drastically over-segmented. 
                # Let's simple-stitch: If the 'title' is identical, merge.
                
                if next_batch.get('title') == current_section.get('title'):
                    # Merge Logic
                    current_section['summary'] += " " + next_batch.get('summary', '')
                    current_section['page_end'] = next_batch.get('page_end')
                    # Merge concepts
                    current_section['metadata']['concepts'].extend(next_batch.get('concepts', []))
                    current_section['metadata']['source_batches'].append(i)
                else:
                    # Finalize current, start new
                    merged_sections.append(current_section)
                    current_section = next_batch
                    current_section['metadata'] = { 
                        "concepts": current_section.get('concepts', []),
                        "source_batches": [i]
                    }
            
            # Append last one
            merged_sections.append(current_section)

        # --- B. Global Aggregations ---
        all_summaries = "\n".join([f"[{s.get('title')}] {s.get('summary')}" for s in merged_sections])
        
        # Global Concepts (Count Frequency from the merged metadata)
        concept_map = {}
        for s in merged_sections:
            for c in s['metadata']['concepts']:
                name = c['name'].lower().strip()
                if name not in concept_map:
                    concept_map[name] = {'count': 0, 'display': c['name']}
                concept_map[name]['count'] += 1
        
        top_concepts = sorted([v['display'] for k, v in concept_map.items()], \
                              key=lambda x: concept_map[x.lower().strip()]['count'], reverse=True)[:20]

        # --- C. Final Summary ---
        reduce_prompt = f"""Write an Executive Summary of this document based on the section summaries below.
Structure:
1. Overview
2. Key Themes
3. Conclusion

Sections:
{all_summaries[:12000]}
"""
        global_summary = "Summary generation failed."
        try:
            global_summary = llm.chat(
                system="You are an expert editor.",
                messages=[{"role": "user", "content": reduce_prompt}]
            )
        except Exception as e:
            logger.error(f"Global reduce failed: {e}")
            global_summary = all_summaries[:2000]

        # Rename keys to match DB model expected keys
        valid_sections = []
        for s in merged_sections:
            valid_sections.append({
                "title": s.get('title'),
                "summary": s.get('summary'),
                "start_page": s.get('page_start'),
                "end_page": s.get('page_end'),
                "metadata": s.get('metadata')
            })

        return global_summary.strip(), valid_sections, top_concepts
