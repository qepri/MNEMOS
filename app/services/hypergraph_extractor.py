from app.extensions import db
from app.models.knowledge_graph import Concept, HyperEdge, HyperEdgeMember
from app.models.document import Document
from app.services.llm_client import get_llm_client
from app.services.embedder import EmbedderService
import json
import logging
from uuid import UUID

logger = logging.getLogger(__name__)

from app.models.chunk import Chunk

logger = logging.getLogger(__name__)

class HypergraphExtractor:
    
    @staticmethod
    def process_document(document_id: str):
        """
        Main entry point to extract hypergraph knowledge from a document.
        Uses Deep Extraction (Chunk-based) to capture detailed concepts and definitions.
        """
        try:
            # Handle UUID vs String input
            oid = document_id
            if isinstance(document_id, str):
                oid = UUID(document_id)

            doc = db.session.get(Document, oid)
            if not doc:
                logger.warning(f"Document {document_id} not found for extraction.")
                return

            logger.info(f"Starting Deep Hypergraph Extraction for doc {document_id}")
            
            # 1. Fetch Content (Chunks)
            chunks = db.session.query(Chunk).filter_by(document_id=doc.id).order_by(Chunk.chunk_index).all()
            
            batches = []
            if chunks:
                logger.info(f"Found {len(chunks)} chunks. Grouping into batches...")
                # Batch size 4 (approx 2000-3000 chars)
                BATCH_SIZE = 4
                for i in range(0, len(chunks), BATCH_SIZE):
                    batch_chunks = chunks[i:i+BATCH_SIZE]
                    batch_text = "\n---\n".join([c.content for c in batch_chunks])
                    # Store tuple (text, first_chunk_id)
                    batches.append((batch_text, batch_chunks[0].id))
            else:
                logger.warning("No chunks found (legacy doc?). Falling back to Summary if available.")
                if doc.summary:
                    batches.append((doc.summary, None))
                else:
                    logger.error("No content available for extraction.")
                    return

            llm = get_llm_client()
            embedder = EmbedderService()

            total_events = 0
            
            # 2. Process Batches
            for i, batch_data in enumerate(batches):
                context_text, first_chunk_id = batch_data
                logger.info(f"Processing Batch {i+1}/{len(batches)}...")
                
                prompt = """
                You are a network ontology graph maker. Analyze the text to extract scientific knowledge.
                
                Tasks:
                1. Identify specific assertions (Source -> Relation -> Target).
                2. Extract definitions for technical concepts.
                
                Output valid JSON only. Structure:
                {
                  "events": [
                    { "source": ["A"], "relation": "relates to", "target": ["B"] }
                  ],
                  "definitions": {
                    "A": "definition..."
                  }
                }
                DO NOT output multiple JSON objects. MERGE them into one.
                
                Rules:
                - Use precise technical terms.
                - Normalize names (e.g., "this protein" -> "Protein X").
                - Capture up to 10 most important events per batch.
                
                Text:
                """ + context_text

                response = llm.chat(
                    system="You are an expert scientific knowledge graph builder. Output only valid JSON.",
                    messages=[{"role": "user", "content": prompt}]
                )
                
                try:
                    # JSON Parsing
                    clean_json = response.strip()         
                    
                    # Robust extraction: Remove C-style comments // ...
                    import re
                    clean_json = re.sub(r"//.*", "", clean_json)
                    
                    # Robust extraction: Find first and last brace
                    start_idx = clean_json.find("{")
                    end_idx = clean_json.rfind("}")
                    
                    if start_idx != -1 and end_idx != -1:
                        clean_json = clean_json[start_idx:end_idx+1]
                    else:
                        raise json.JSONDecodeError("No JSON braces found", clean_json, 0)

                    data = json.loads(clean_json)
                    events = data.get("events", [])
                    definitions = data.get("definitions", {})
                    
                except Exception as e:
                    logger.warning(f"Failed to parse LLM output for batch {i}: {e}. Response preview: {response[:100]}...")
                    continue

                # 3. Process Definitions (Update Concepts)
                for concept_name, definition_val in definitions.items():
                    norm_name = concept_name.strip().lower()
                    if not norm_name or not definition_val: continue
                    
                    # Handle nested dicts if the LLM hallucinates structure (e.g. {"definition": "..."})
                    final_def = definition_val
                    if isinstance(definition_val, dict):
                         final_def = definition_val.get("definition") or definition_val.get("description") or str(definition_val)
                    
                    if not isinstance(final_def, str):
                        final_def = str(final_def)

                    # Quick lookup
                    concept = db.session.query(Concept).filter_by(name=norm_name).first()
                    if concept:
                        if not concept.description:
                            concept.description = final_def
                            db.session.add(concept)
                            logger.info(f"Updated definition for '{norm_name}'")
                    # Note: We don't create concepts just from definitions, we wait for events to link them.
                    # Or should we? Better to wait for usage in an edge to avoid orphan noise.

                # 4. Process Events
                for edge_item in events:
                    sources = edge_item.get("source", [])
                    targets = edge_item.get("target", [])
                    relation = edge_item.get("relation", "relates to")
                    
                    if isinstance(sources, str): sources = [sources]
                    if isinstance(targets, str): targets = [targets]
                    
                    if not sources or not targets: continue
                    
                    concept_names = sources + targets
                    description = f"{', '.join(sources)} {relation} {', '.join(targets)}"
                    
                    # Entity Resolution & Creation
                    concept_objs = []
                    for name in concept_names:
                        norm_name = name.strip().lower()
                        if not norm_name: continue
                        
                        # Check Cache/DB
                        concept = db.session.query(Concept).filter_by(name=norm_name).first()
                        
                        if not concept:
                            # Fuzzy Match
                            name_embedding = embedder.embed([norm_name])[0]
                            closest = db.session.query(Concept).order_by(
                                Concept.embedding.cosine_distance(name_embedding)
                            ).limit(1).first()
                            
                            if closest:
                                dist = db.session.query(Concept.embedding.cosine_distance(name_embedding)).filter(Concept.id == closest.id).scalar()
                                if dist is not None and dist < 0.15:
                                    concept = closest
                        
                        if not concept:
                            # Create New
                            concept = Concept(name=norm_name)
                            concept.embedding = embedder.embed([norm_name])[0]
                            # Check if we have a definition waiting
                            # (Naive check: capitalized key matches?)
                            # Better: check lowercased dictionary
                            for def_key, def_val in definitions.items():
                                if def_key.strip().lower() == norm_name:
                                    # Handle nested structs
                                    final_def = def_val
                                    if isinstance(def_val, dict):
                                         final_def = def_val.get("definition") or def_val.get("description") or str(def_val)
                                    concept.description = str(final_def)
                                    break
                                    
                            db.session.add(concept)
                            db.session.flush()
                        
                        if concept not in concept_objs:
                            concept_objs.append(concept)
                    
                    if len(concept_objs) < 2: continue

                    # Create HyperEdge
                    # Check for duplicates? (Optional enhancement)
                    # For now just append to allow multi-context assertions
                    
                    hyper_edge = HyperEdge(
                        description=description,
                        source_document_id=doc.id,
                        source_chunk_id=first_chunk_id
                    )
                    hyper_edge.embedding = embedder.embed([description])[0]
                    db.session.add(hyper_edge)
                    db.session.flush()
                    
                    for c in concept_objs:
                        role = "participant"
                        if c.name in [s.strip().lower() for s in sources]: role = "source"
                        elif c.name in [t.strip().lower() for t in targets]: role = "target"
                        
                        member = HyperEdgeMember(
                            hyper_edge_id=hyper_edge.id, 
                            concept_id=c.id, 
                            role=role
                        )
                        db.session.add(member)
                    
                    total_events += 1
                
                # Commit per batch to save progress
                db.session.commit()
            
            logger.info(f"Hypergraph extraction complete. Extracted {total_events} events.")
            
        except Exception as e:
            logger.error(f"Error in HypergraphExtractor: {e}")
            db.session.rollback()
