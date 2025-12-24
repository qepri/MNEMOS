from app.extensions import db
from sqlalchemy import text

def upgrade():
    with db.engine.connect() as conn:
        conn.execute(text("ALTER TABLE user_preferences ADD COLUMN IF NOT EXISTS custom_api_key VARCHAR(255)"))
        conn.commit()
    print("Added custom_api_key column to user_preferences table")

if __name__ == "__main__":
    from app import create_app
    app = create_app()
    with app.app_context():
        upgrade()
