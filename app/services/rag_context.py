"""Hierarchical context assembly for RAG answers.

Groups retrieved content as Document -> Section -> Chunk so the prompt keeps
structure while staying inside the token budget. Extracted from RAGService to
keep that class focused on retrieval.
"""

import logging
from typing import List, Union

from app.models.chunk import Chunk
from app.models.document import Document
from app.models.section import DocumentSection

logger = logging.getLogger(__name__)


def _format_time(seconds: float) -> str:
    """Convert seconds to MM:SS or HH:MM:SS."""
    if seconds is None: return ""
    hours, remainder = divmod(int(seconds), 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


def build_hierarchical_context(db, chunks: List[Chunk], graph_results: List[Union[DocumentSection, Chunk]]):
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
                doc = item.document if item.document else db.query(Document).get(item.document_id)
            else:
                doc = item.document if item.document else db.query(Document).get(item.document_id)
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
