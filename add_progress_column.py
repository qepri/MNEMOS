"""
Migration script to add processing_progress column to documents table.
Run this once to update the database schema.
"""
from app import create_app
from app.extensions import db
from sqlalchemy import text

def add_progress_column():
    app = create_app()

    with app.app_context():
        try:
            # Check if column already exists
            result = db.session.execute(text("""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name='documents' AND column_name='processing_progress'
            """))

            if result.fetchone():
                print("✓ Column 'processing_progress' already exists. No migration needed.")
                return

            # Add the column
            print("Adding 'processing_progress' column to documents table...")
            db.session.execute(text("""
                ALTER TABLE documents
                ADD COLUMN processing_progress INTEGER DEFAULT 0
            """))

            # Update existing rows
            print("Updating existing documents...")
            db.session.execute(text("""
                UPDATE documents
                SET processing_progress = CASE
                    WHEN status = 'completed' THEN 100
                    WHEN status = 'processing' THEN 50
                    WHEN status = 'error' THEN 0
                    ELSE 0
                END
            """))

            db.session.commit()
            print("✓ Migration completed successfully!")
            print("  - Added processing_progress column")
            print("  - Updated existing documents")

        except Exception as e:
            db.session.rollback()
            print(f"✗ Migration failed: {e}")
            raise

if __name__ == "__main__":
    add_progress_column()
