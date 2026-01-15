from app.extensions import db
from sqlalchemy import text

def upgrade():
    with db.engine.connect() as conn:
        # Add provider column, default to 'duckduckgo'
        conn.execute(text("ALTER TABLE user_preferences ADD COLUMN IF NOT EXISTS web_search_provider VARCHAR(50) DEFAULT 'duckduckgo'"))
        
        # Add API keys
        conn.execute(text("ALTER TABLE user_preferences ADD COLUMN IF NOT EXISTS tavily_api_key VARCHAR(255)"))
        conn.execute(text("ALTER TABLE user_preferences ADD COLUMN IF NOT EXISTS brave_search_api_key VARCHAR(255)"))
        
        conn.commit()
    print("Added web search provider columns to user_preferences table")

if __name__ == "__main__":
    from app import create_app
    app = create_app()
    with app.app_context():
        upgrade()
