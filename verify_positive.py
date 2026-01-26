
import sys
import os

# Add the project root to the python path
sys.path.append(os.getcwd())

from app import create_app
from app.extensions import db
from app.services.rag import RAGService
from app.models.document import Document

def verify_positive_filtering(query_text="humpty"):
    app = create_app()
    with app.app_context():
        rag_service = RAGService(db.session)
        
        # 1. Fetch the specific document we know has "Humpty" content
        # Based on previous logs: "Ccru - Ccru_ Writings..."
        target_doc = Document.query.filter(Document.original_filename.ilike("%Ccru%")).first()
        
        if not target_doc:
            print("[ERROR] TARGET DOCUMENT NOT FOUND.")
            # Fallback to any doc if specific one missing, but might fail concept check
            target_doc = Document.query.first()
            
        print(f"\n==================================================")
        print(f"Testing POSITIVE Filtering: '{query_text}'")
        print(f"Target Document: {target_doc.original_filename} (ID: {target_doc.id})")
        print(f"==================================================")
        
        # 2. Call Query with Filtering for the CORRECT doc
        result = rag_service.query(
            query_text, 
            document_ids=[str(target_doc.id)], 
            use_graph_rag=True
        )
        
        sources = result.get('sources', [])
        graph_nodes = [s for s in sources if s.get('type') == 'graph_node']
        
        print(f"\nFound {len(sources)} sources.")
        print(f"Found {len(graph_nodes)} graph nodes.")
        
        # 3. Verify
        if len(graph_nodes) > 0:
            print("[SUCCESS] Graph nodes returned for selected document.")
            for node in graph_nodes:
                print(f" - {node.get('location')} (DocID: {node.get('document_id')})")
                if node.get('document_id') != str(target_doc.id):
                     print("   [WARNING] Node has mismatching ID? (Should technically be impossible due to filter)")
        else:
            print("[FAILURE] No graph nodes returned! Filtering might be too aggressive or concept missing.")

if __name__ == "__main__":
    verify_positive_filtering("humpty")
