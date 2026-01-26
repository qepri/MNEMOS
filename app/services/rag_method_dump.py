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
                doc = section.document
                docs_map[d_id] = {'obj': doc, 'sections': {}, 'orphans': []}
            
            s_id = str(section.id) if section.id else "virtual_graph_section"
            if s_id not in docs_map[d_id]['sections']:
                 docs_map[d_id]['sections'][s_id] = {'obj': section, 'chunks': [], 'is_graph': True}
            
            # Graph sections are their own content, often without sub-chunks in this specific flow.
            # We treat the section content itself as the "chunk".
            # If it's a "fake_section" from a chunk (see _retrieve_via_graph), it has content.
            
            sources.append({
                "document": section.document.original_filename,
                "document_id": str(section.document.id),
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
