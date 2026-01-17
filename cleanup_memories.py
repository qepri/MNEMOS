from app import create_app
from app.extensions import db
from app.models.memory import UserMemory

app = create_app()

with app.app_context():
    # Find memories starting with "Error communicating"
    bad_memories = UserMemory.query.filter(UserMemory.content.like('Error %')).all()
    count = len(bad_memories)
    
    if count > 0:
        print(f"Found {count} invalid memories. Deleting...")
        for mem in bad_memories:
            db.session.delete(mem)
        db.session.commit()
        print("Cleanup complete.")
    else:
        print("No invalid memories found.")
