from app import create_app
from app.extensions import db
from sqlalchemy import text
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def update_schema():
    app = create_app()
    with app.app_context():
        try:
            # 1. Create llm_connections table (handled by create_all usually, but explicit here is safe)
            db.create_all()
            logger.info("Checked/Created tables.")

            # 2. Add column active_connection_id to user_preferences if not exists
            # PostgreSQL syntax
            with db.engine.connect() as conn:
                try:
                    conn.execute(text("ALTER TABLE user_preferences ADD COLUMN active_connection_id UUID REFERENCES llm_connections(id)"))
                    conn.commit()
                    logger.info("Added active_connection_id column.")
                except Exception as e:
                    if "already exists" in str(e):
                        logger.info("Column active_connection_id already exists.")
                    else:
                        logger.error(f"Error adding column: {e}")
                        # Don't re-raise, might be other issues, but we want to proceed if it exists
        except Exception as e:
            logger.error(f"Schema update failed: {e}")

if __name__ == "__main__":
    update_schema()
