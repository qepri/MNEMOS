
import sys
import os

# Add the project root to the python path
sys.path.append(os.getcwd())

from app import create_app
from app.extensions import db
from app.services.rag import RAGService
from app.models.document import Document

def verify_filtering(query_text="humpty"):
    app = create_app()
    with app.app_context():
        rag_service = RAGService(db.session)
        
        # 1. Fetch documents
        docs = Document.query.limit(2).all()
        if len(docs) < 1:
            print("[ERROR] Need at least 1 document.")
            return

        target_doc = docs[0]
        other_doc_id = str(docs[1].id) if len(docs) > 1 else "fake-id"
        
        print(f"\n==================================================")
        print(f"Testing Filtering: '{query_text}'")
        print(f"Target Document: {target_doc.original_filename} (ID: {target_doc.id})")
        if len(docs) > 1:
            print(f"Other Document: {docs[1].original_filename} (ID: {docs[1].id})")
        print(f"==================================================")
        
        # 2. Call Query with Filtering
        result = rag_service.query(
            query_text, 
            document_ids=[str(target_doc.id)], 
            use_graph_rag=True
        )
        
        sources = result.get('sources', [])
        print(f"\nFound {len(sources)} sources.")
        
        graph_nodes = [s for s in sources if s.get('type') == 'graph_node']
        print(f"Found {len(graph_nodes)} graph nodes.")
        
        # 3. Verify
        all_match = True
        for node in graph_nodes:
            node_doc_id = node.get('document_id')
            print(f" - Node: {node.get('location')} | DocID: {node_doc_id}")
            
            if node_doc_id and node_doc_id != str(target_doc.id):
                print(f"   [FAIL] Node belongs to wrong document: {node_doc_id}")
                all_match = False
            elif node_doc_id == str(target_doc.id):
                print(f"   [PASS] Matches target.")
            else:
                print(f"   [WARN] No Document ID on node.")

        if all_match:
            print("\n[SUCCESS] All graph nodes match the target document (or have no ID).")
        else:
            print("\n[FAILURE] Found graph nodes from other documents!")

if __name__ == "__main__":
    verify_filtering("humpty")
