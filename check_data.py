from app import create_app, db
from app.models.knowledge_graph import Concept, HyperEdge
from sqlalchemy import text

app = create_app()

with app.app_context():
    try:
        # Check if tables exist
        inspector = db.inspect(db.engine)
        tables = inspector.get_table_names()
        print(f"Tables found: {tables}")
        
        if 'concepts' not in tables:
            print("ERROR: 'concepts' table missing!")
        else:
            c_count = db.session.query(Concept).count()
            print(f"Concepts Count: {c_count}")
            
        if 'hyper_edges' not in tables:
            print("ERROR: 'hyper_edges' table missing!")
        else:
            e_count = db.session.query(HyperEdge).count()
            print(f"HyperEdges Count: {e_count}")

        # Check raw SQL just in case
        with db.engine.connect() as conn:
            result = conn.execute(text("SELECT count(*) FROM concepts"))
            print(f"Raw SQL Concept Count: {result.scalar()}")

    except Exception as e:
        print(f"Error: {e}")
