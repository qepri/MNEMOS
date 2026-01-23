from app.extensions import db
from app.models.document import Document
from app.models.chunk import Chunk
from app.services.llm_client import get_llm_client, reset_client
from app.services.embedder import EmbedderService
import logging
from uuid import UUID

logger = logging.getLogger(__name__)

import json
import re

class SummaryService:
    @staticmethod
    def generate_summary(document_id: str):
        """
        Generates a summary using Map-Reduce pattern.
        1. Map: Batch chunks -> Section Summary + Structure + Concepts
        2. Reduce: Combine -> Global Summary + Master Structure + Top Concepts
        """
        try:
            logger.info(f"Generating summary (Map-Reduce) for doc {document_id}")
            
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
            llm = get_llm_client()

            # 3. MAP PHASE: Batch Processing
            BATCH_SIZE = 5 # Adjust based on chunk size (~500 chars * 5 = 2500 chars)
            map_results = []
            
            logger.info(f"Starting Map Phase for {len(chunks)} chunks in batches of {BATCH_SIZE}...")
            
            for i in range(0, len(chunks), BATCH_SIZE):
                batch_chunks = chunks[i : i + BATCH_SIZE]
                batch_text = "\n".join([f"[Page {c.page_number or '?'}] {c.content}" for c in batch_chunks])
                
                # Extract Section info
                section_data = SummaryService._map_process_batch(llm, batch_text, i // BATCH_SIZE)
                if section_data:
                    map_results.append(section_data)

            # 4. REDUCE PHASE: Aggregate results
            logger.info("Starting Reduce Phase...")
            global_summary, global_structure, global_concepts = SummaryService._reduce_results(llm, map_results)

            # 5. Save to Document
            doc.summary = global_summary
            
            # Initialize metadata if null
            if doc.metadata_ is None:
                doc.metadata_ = {}
            
            # Save Global Concepts to metadata
            doc.metadata_['key_concepts'] = global_concepts
            
            # 6. Save Chapters to 'document_sections' Table (Vectorized)
            from app.models.section import DocumentSection
            
            # Clear old sections if any
            db.session.query(DocumentSection).filter_by(document_id=doc.id).delete()
            
            logger.info(f"Saving {len(global_structure)} vectorized sections...")
            embedder = EmbedderService()
            
            for chapter in global_structure:
                title = chapter.get('title', 'Untitled Section')
                content = chapter.get('summary', '') 
                # If no summary explicitly attached, fallback to title or placeholder
                if not content: content = f"Section: {title}"
                
                # Embed content for semantic search
                embedding = embedder.embed([content])[0]
                
                section = DocumentSection(
                    document_id=doc.id,
                    title=title,
                    content=content,
                    start_page=chapter.get('page'), # map_process returns 'page'
                    end_page=chapter.get('page'),   # naive assumption, can refine range later
                    embedding=embedding
                )
                db.session.add(section)
            
            # Embed Final Summary
            logger.info("Embedding final global summary...")
            summary_vec = embedder.embed([global_summary])[0]
            doc.summary_embedding = summary_vec
            
            doc.processing_progress = 85
            db.session.commit()
            
            logger.info("Summary generation complete.")
            return global_summary

        except Exception as e:
            logger.error(f"Failed to generate summary: {e}")
            raise e

    @staticmethod
    def _map_process_batch(llm, text_content: str, batch_index: int):
        """
        MAP STEP: Summarize a single batch and extract structure/concepts.
        """
        try:
            prompt = f"""Analyze the following text segment from a larger document.
Return a JSON object with this EXACT structure (no markdown, no extra text):
{{
    "summary": "A concise paragraph summarizing this section.",
    "chapters": [
        {{ "title": "Chapter/Section Title found (if any)", "page": 12 }}
    ],
    "concepts": ["Concept 1", "Concept 2"] 
}}

Limit 'concepts' to the top 3 most important entities in this segment.
If no explicit chapter/section title exists, leave "chapters" empty [].

Text Segment:
{text_content[:3500]} 
""" # Limit context to avoid overflow

            response = llm.chat(
                system="You are a precise data extractor. Output valid, separate JSON only.",
                messages=[{"role": "user", "content": prompt}]
            )
            
            # Clean response (strip code blocks)
            clean_json = response.strip()
            if clean_json.startswith("```json"):
                clean_json = clean_json[7:]
            if clean_json.endswith("```"):
                clean_json = clean_json[:-3]
            
            data = json.loads(clean_json)
            return data
            
        except Exception as e:
            logger.warning(f"Map step failed for batch {batch_index}: {e}")
            return None

    @staticmethod
    def _reduce_results(llm, map_results):
        """
        REDUCE STEP: Combine map outputs into global metadata.
        """
        # 1. Concatenate Summaries
        combined_summaries = "\n\n".join([f"[Section {i+1}] {r.get('summary', '')}" for i, r in enumerate(map_results)])
        
        # 2. Aggregate Structure directly
        global_structure = []
        for r in map_results:
            batch_summary = r.get('summary', '')
            if 'chapters' in r and isinstance(r['chapters'], list):
                for chapter in r['chapters']:
                    # Attach the summary of the section where this chapter was found
                    # This serves as the "Chapter Summary" context
                    chapter['summary'] = batch_summary
                global_structure.extend(r['chapters'])
        
        # 3. Aggregate Concepts (Frequency Count)
        concept_freq = {}
        for r in map_results:
            for c in r.get('concepts', []):
                c_clean = c.strip().title()
                concept_freq[c_clean] = concept_freq.get(c_clean, 0) + 1
        
        # Top 20 concepts by frequency, then appearance
        top_concepts = sorted(concept_freq.keys(), key=lambda x: concept_freq[x], reverse=True)[:20]

        # 4. Generate Global Summary (Final LLM Pass)
        reduce_prompt = f"""Synthesize the following section summaries into one cohesive 'Global Executive Summary' of the entire document.
Write 3-4 distinct paragraphs. Focus on the narrative arc, core arguments, and final conclusions.

Section Summaries:
{combined_summaries[:10000]}
"""
        global_summary = "Summary generation failed."
        try:
            global_summary = llm.chat(
                system="You are an expert editor.",
                messages=[{"role": "user", "content": reduce_prompt}]
            )
        except Exception as e:
            logger.error(f"Reduce step (Final content) failed: {e}")
            global_summary = combined_summaries[:2000] # Fallback
            
        return global_summary.strip(), global_structure, top_concepts
