from app.extensions import db
from app.models.knowledge_graph import Concept, HyperEdge, HyperEdgeMember
from app.models.document import Document
from app.services.llm_client import get_llm_client
from app.services.embedder import EmbedderService
import json
import logging
from uuid import UUID

logger = logging.getLogger(__name__)

class HypergraphExtractor:
    
    @staticmethod
    def process_document(document_id: str):
        """
        Main entry point to extract hypergraph knowledge from a document.
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

            logger.info(f"Extracting Hypergraph for doc {document_id}")
            
            # 1. LLM Extraction
            llm = get_llm_client()
            
            # Context Preparation: Use summary if available, else generate it
            context_text = doc.summary
            if not context_text:
                logger.info("Document has no summary. Triggering Summary Generation...")
                try:
                    from app.services.summary_service import SummaryService
                    context_text = SummaryService.generate_summary(doc.id)
                    if not context_text:
                         logger.warning("Summary generation failed or returned empty. Aborting extraction.")
                         return
                    
                    # Refresh doc to get the summary (though we have the text, good to be safe)
                    db.session.refresh(doc) # This might not be needed if session is same, but safe
                except Exception as e:
                    logger.error(f"Failed to generate summary during hypergraph extraction: {e}")
                    return

            prompt = """
            You are a network ontology graph maker who extracts precise Subject–Verb–Object triples from a given context.
            
            Task:
            1. Analyze the text to identify specific scientific assertions.
            2. Extract "events" where specific "source" entities relate to "target" entities via a specific "relation".
            3. Use exact technical terms. Normalize vague terms (e.g., "this material" -> "nHAp composite").
            4. Output a JSON object with a single key "events".

            Format:
            {
              "events": [
                {
                  "source": ["Concept A", "Concept B"], 
                  "relation": "specific verb phrase", 
                  "target": ["Concept C"]
                }
              ]
            }

            Output specification:
            - "source" and "target" must be lists of strings.
            - "relation" must be a string.
            - Limit to the top 10 most mechanistically important events.

            Text:
            """ + context_text
            
            response = llm.chat(
                system="You are an expert scientific knowledge graph builder. Output only valid JSON.",
                messages=[{"role": "user", "content": prompt}]
            )
            
            try:
                # Naive JSON cleaning
                clean_json = response.strip().replace("```json", "").replace("```", "")
                edges_data_raw = json.loads(clean_json)
                # Handle both list (old) and dict (new) formats just in case
                if isinstance(edges_data_raw, dict) and "events" in edges_data_raw:
                    edges_data = edges_data_raw["events"]
                elif isinstance(edges_data_raw, list):
                    edges_data = edges_data_raw
                else:
                    edges_data = [] # Invalid format
            except json.JSONDecodeError:
                logger.error(f"Failed to parse LLM output for doc {document_id}: {response}")
                return

            # 2. Entity Resolution & Storage
            embedder = EmbedderService()
            
            # Pre-calc embeddings for all unique concept names in this batch to save time?
            # For now, do it iteratively for simplicity.
            
            for edge_item in edges_data:
                # SVO Format Support
                if "source" in edge_item and "target" in edge_item:
                    sources = edge_item.get("source", [])
                    targets = edge_item.get("target", [])
                    relation = edge_item.get("relation", "relates to")
                    
                    # Flatten list if needed (some LLMs output string instead of list)
                    if isinstance(sources, str): sources = [sources]
                    if isinstance(targets, str): targets = [targets]
                    
                    concept_names = sources + targets
                    description = f"{', '.join(sources)} {relation} {', '.join(targets)}"
                else:
                    # Fallback to old "description" + "concepts" format
                    description = edge_item.get("description")
                    concept_names = edge_item.get("concepts", [])
                
                if not description or len(concept_names) < 2:
                    continue
                
                # Create/Get Concepts
                concept_objs = []
                for name in concept_names:
                    # Normalize name
                    norm_name = name.strip().lower()
                    if not norm_name: continue
                    
                    # Generate embedding FIRST
                    name_embedding = embedder.embed([norm_name])[0]
                    
                    # 1. Exact Match Check (Fastest)
                    concept = db.session.query(Concept).filter_by(name=norm_name).first()
                    
                    if not concept:
                        # 2. Fuzzy Vector Match (Cos Sim)
                        # Threshold 0.15 (approx 0.85 similarity)
                        closest = db.session.query(Concept).order_by(
                            Concept.embedding.cosine_distance(name_embedding)
                        ).limit(1).first()
                        
                        if closest:
                            # Check actual distance
                            # We need a separate query or trust the order. 
                            # Let's verify distance.
                            dist = db.session.query(
                                Concept.embedding.cosine_distance(name_embedding)
                            ).filter(Concept.id == closest.id).scalar()
                            
                            if dist is not None and dist < 0.15:
                                logger.info(f"Fuzzy Resolved: '{norm_name}' -> '{closest.name}' (dist: {dist:.3f})")
                                concept = closest
                    
                    if not concept:
                        # Create New
                        logger.info(f"Creating new Concept: {norm_name}")
                        concept = Concept(name=norm_name)
                        concept.embedding = name_embedding
                        db.session.add(concept)
                        db.session.flush() # get ID
                    
                    if concept not in concept_objs:
                        concept_objs.append(concept)
                
                if len(concept_objs) < 2:
                    continue

                # Create HyperEdge
                logger.info(f"Creating HyperEdge: {description[:50]}...")
                hyper_edge = HyperEdge(
                    description=description,
                    source_document_id=doc.id
                )
                hyper_edge.embedding = embedder.embed([description])[0]
                db.session.add(hyper_edge)
                db.session.flush()
                
                # Link Members
                for c in concept_objs:
                    # Precise Role Assignment
                    role = "participant" # default
                    
                    # Check if this concept's name was in the source list
                    # We compare lowercased names
                    if c.name in [s.strip().lower() for s in sources]:
                        role = "source"
                    elif c.name in [t.strip().lower() for t in targets]:
                        role = "target"
                    
                    member = HyperEdgeMember(
                        hyper_edge_id=hyper_edge.id,
                        concept_id=c.id,
                        role=role
                    )
                    db.session.add(member)
            
            db.session.commit()
            logger.info(f"Hypergraph extraction complete for doc {document_id}")
            
        except Exception as e:
            logger.error(f"Error in HypergraphExtractor: {e}")
            db.session.rollback()
