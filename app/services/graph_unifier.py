from app.extensions import db
from app.models.section import DocumentSection
from app.models.knowledge_graph import Concept, HyperEdge, HyperEdgeMember
from app.services.embedder import EmbedderService
from uuid import UUID
import logging

logger = logging.getLogger(__name__)

class GraphUnifierService:
    """
    Service to promote local JSON metadata (from DocumentSection) 
    into global Knowledge Graph nodes (Concepts and HyperEdges).
    """

    @staticmethod
    def process_section(section_id: str):
        """
        Reads a DocumentSection, extracts concepts from metadata, 
        and updates the Knowledge Graph.
        """
        try:
            section = db.session.get(DocumentSection, UUID(section_id))
            if not section:
                logger.error(f"GraphUnifier: Section {section_id} not found")
                return

            metadata = section.metadata_ or {}
            # Support both keys and formats (list of strings or list of dicts)
            raw_concepts = metadata.get("concepts", []) or metadata.get("key_concepts", [])

            if not raw_concepts:
                logger.info(f"GraphUnifier: No concepts found for section {section.title}")
                return

            # Extract names depending on format
            concepts_list = []
            for c in raw_concepts:
                if isinstance(c, dict):
                    name = c.get("name")
                    if name: concepts_list.append(name)
                elif isinstance(c, str):
                    concepts_list.append(c)

            logger.info(f"GraphUnifier: Processing {len(concepts_list)} concepts for section '{section.title}'")

            # 1. Ensure Concepts Exist (Global) - Bulk Optimized
            concept_map = {} # Name -> UUID
            
            # Prepare names for bulk query
            unique_names = list(set([n.strip() for n in concepts_list if n.strip()]))
            if not unique_names:
                return

            # Bulk Fetch Existing Concepts
            # We use ilike in a sophisticated way or normalize to lowercase for comparison
            # Ideally, we store standardized names. Here we fetch all that match in lowercase.
            from sqlalchemy import func
            existing_concepts = Concept.query.filter(
                func.lower(Concept.name).in_([n.lower() for n in unique_names])
            ).all()

            # Populate map with existing
            # We create a lookup dict: lowercase_name -> Concept Object
            existing_lookup = {c.name.lower(): c.id for c in existing_concepts}

            for original_name in unique_names:
                lower_name = original_name.lower()
                
                if lower_name in existing_lookup:
                    # Found existing
                    concept_map[original_name] = existing_lookup[lower_name]
                else:
                    # Create New
                    logger.info(f"GraphUnifier: Generating embedding for new concept '{original_name}'")
                    try:
                        embedding = EmbedderService().embed([original_name])[0]
                    except Exception as e:
                        logger.error(f"Failed to embed concept '{original_name}': {e}")
                        embedding = None

                    new_concept = Concept(
                        name=original_name, # Use original casing for creation
                        description="Extracted from document summary", 
                        embedding=embedding
                    )
                    db.session.add(new_concept)
                    db.session.flush() # Get ID
                    
                    # Add to map so we don't try to create it again if duplicates exist in list
                    concept_map[original_name] = new_concept.id
                    existing_lookup[lower_name] = new_concept.id
                    
                    logger.info(f"GraphUnifier: Created new concept '{original_name}' with embedding")

            # 2. Create HyperEdge (The Link)
            # We create ONE hyperedge representing "This section discusses these concepts"
            
            edge_desc = f"Section Summary: {section.title}"
            
            # Check if edge already exists to prevent duplicates on re-runs
            existing_edge = HyperEdge.query.filter_by(source_section_id=section.id).first()
            
            if existing_edge:
                hex_edge = existing_edge
                # Optional: Clear members and re-add? For now, we skip if exists.
                logger.info(f"GraphUnifier: Edge already exists for section {section.id}, skipping creation.")
                pass 
            else:
                hex_edge = HyperEdge(
                    description=edge_desc,
                    source_document_id=section.document_id,
                    source_section_id=section.id
                    # source_chunk_id is null as this is section-level
                )
                db.session.add(hex_edge)
                db.session.flush()
                
                # 3. Add Members
                for name, cid in concept_map.items():
                    member = HyperEdgeMember(
                        hyper_edge_id=hex_edge.id,
                        concept_id=cid,
                        role="topic"
                    )
                    db.session.add(member)
                
                logger.info(f"GraphUnifier: Linked {len(concept_map)} concepts to section {section.id}")

            db.session.commit()

        except Exception as e:
            logger.error(f"GraphUnifier Error: {e}")
            db.session.rollback()
