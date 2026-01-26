import sys
import os

# Add the project root to the python path
sys.path.append(os.getcwd())

from app import create_app
from app.extensions import db
from app.models.knowledge_graph import Concept, HyperEdge, HyperEdgeMember
from app.models.section import DocumentSection
from sqlalchemy import func

def debug_concept(name_query):
    app = create_app()
    with app.app_context():
        print(f"--- Debugging Concept: '{name_query}' ---")
        
        # 1. Find the Concept
        concepts = Concept.query.filter(Concept.name.ilike(f"%{name_query}%")).all()
        
        if not concepts:
            print(f"No concept found matching '{name_query}'")
            return

        for c in concepts:
            print(f"\n[Concept] ID: {c.id} | Name: {c.name}")
            
            # 2. Check Memberships
            members = HyperEdgeMember.query.filter_by(concept_id=c.id).all()
            print(f"  > Found {len(members)} HyperEdgeMembers")
            
            if not members:
                print("  > WARNING: Concept exists but has no HyperEdgeMembers (Isolated Node)")
                continue

            for m in members:
                print(f"    - Member ID: {m.id} | Role: {m.role} | HyperEdge ID: {m.hyper_edge_id}")
                
                # 3. Check HyperEdge
                edge = HyperEdge.query.get(m.hyper_edge_id)
                if not edge:
                    print("      > ERROR: HyperEdge not found!")
                    continue
                
                print(f"      > [Edge] ID: {edge.id} | Desc: {edge.description} | SectionID: {edge.source_section_id}")
                
                if edge.source_section_id:
                    # 4. Check Section
                    section = DocumentSection.query.get(edge.source_section_id)
                    if section:
                        print(f"        > [Section] Found: '{section.title}' (ID: {section.id})")
                    else:
                        print(f"        > ERROR: Section ID {edge.source_section_id} not found in document_sections table")
                else:
                    print("        > Edge has NO Source Section ID (Global Edge?)")

if __name__ == "__main__":
    debug_concept("humpty")
