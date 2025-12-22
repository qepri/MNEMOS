"""Run database migrations."""
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app import create_app
from app.extensions import db
from app.models.user_preferences import UserPreferences, SystemPrompt

def run_migration():
    """Create tables and insert default data."""
    app = create_app()

    with app.app_context():
        print("Creating tables...")
        db.create_all()

        # Check if default system prompt exists
        default_prompt = SystemPrompt.query.filter_by(is_default=True).first()

        if not default_prompt:
            print("Creating default system prompt...")
            default_prompt = SystemPrompt(
                title='Default RAG Assistant',
                content="""You are a helpful assistant that answers questions based ONLY on the provided context.
        If the information is not in the context, say so.
        Always cite the sources using the filename and timestamp/page number when relevant.
        Provide detailed and comprehensive answers. Use markdown (bold, lists, headers) to structure your response.""",
                is_default=True,
                is_editable=False
            )
            db.session.add(default_prompt)
            db.session.commit()
            print(f"✓ Default prompt created: {default_prompt.id}")
        else:
            print(f"✓ Default prompt already exists: {default_prompt.id}")

        # Check if user preferences exist
        prefs = UserPreferences.query.first()

        if not prefs:
            print("Creating default user preferences...")
            prefs = UserPreferences(
                use_conversation_context=True,
                max_context_messages=10,
                selected_system_prompt_id=default_prompt.id
            )
            db.session.add(prefs)
            db.session.commit()
            print(f"✓ User preferences created: {prefs.id}")
        else:
            print(f"✓ User preferences already exist: {prefs.id}")

        print("\n✓ Migration completed successfully!")

if __name__ == '__main__':
    run_migration()
