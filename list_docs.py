
import sys
import os
sys.path.append(os.getcwd())
from app import create_app
from app.models.document import Document

app = create_app()
with app.app_context():
    docs = Document.query.all()
    print(f"Found {len(docs)} documents.")
    for d in docs:
        print(f" - {d.original_filename} (ID: {d.id})")
