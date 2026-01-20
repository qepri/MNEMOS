from flask import Flask
from config.settings import settings
from app.extensions import db, migrate, celery_app

def create_app():
    app = Flask(__name__)

    # Disable Flask's strict slashes to avoid redirect issues with nginx proxy
    app.url_map.strict_slashes = False

    # Configure app from settings
    app.config["SQLALCHEMY_DATABASE_URI"] = settings.DATABASE_URL
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["SECRET_KEY"] = settings.SECRET_KEY
    app.config["MAX_CONTENT_LENGTH"] = settings.MAX_CONTENT_LENGTH
    app.config.from_prefixed_env()

    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)
    
    # Configure Celery
    celery_app.conf.update(app.config)

    # Register Blueprints
    from app.api.documents import bp as documents_bp
    from app.api.chat import bp as chat_bp
    from app.web import bp as web_bp
    from app.api.conversations import bp as conversations_bp
    from app.api.settings import bp as settings_bp
    from app.api.connections import bp as connections_bp
    from app.api.ollama_manage import bp as ollama_manage_bp # Changed: Import ollama_manage_bp
    from app.api.collections import bp as collections_bp
    
    app.register_blueprint(documents_bp)
    app.register_blueprint(collections_bp)
    app.register_blueprint(chat_bp)
    app.register_blueprint(web_bp)
    app.register_blueprint(conversations_bp)
    app.register_blueprint(settings_bp, url_prefix='/api/settings') # Changed: Added url_prefix
    app.register_blueprint(connections_bp)
    app.register_blueprint(ollama_manage_bp, url_prefix='/api/settings/ollama')
    
    from app.api.memory import bp as memory_bp
    app.register_blueprint(memory_bp, url_prefix='/api/memory')

    from app.api.voice import voice_bp
    app.register_blueprint(voice_bp, url_prefix='/api/voice')
    
    from sqlalchemy import text
    from sqlalchemy.exc import SQLAlchemyError
    # Import models to ensure they are registered with SQLAlchemy
    with app.app_context():
        try:
            # Ensure pgvector extension exists
            db.session.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            db.session.commit()
        except SQLAlchemyError:
            db.session.rollback()
            # Ignore race condition if multiple workers try to create it
            pass
        
        try:
            # This import is necessary for Alembic to detect models
            from app import models
            db.create_all()
            
            # Auto-migration for new features without full Alembic reset
            try:
                 db.session.execute(text("ALTER TABLE user_preferences ADD COLUMN IF NOT EXISTS active_connection_id UUID REFERENCES llm_connections(id)"))
                 db.session.commit()
                 
                 db.session.execute(text("ALTER TABLE llm_connections ADD COLUMN IF NOT EXISTS models JSONB DEFAULT '[]'"))
                 db.session.commit()
                 
                 # Voice Settings Migration
                 db.session.execute(text("ALTER TABLE user_preferences ADD COLUMN IF NOT EXISTS tts_provider VARCHAR(50) DEFAULT 'browser' NOT NULL"))
                 db.session.execute(text("ALTER TABLE user_preferences ADD COLUMN IF NOT EXISTS stt_provider VARCHAR(50) DEFAULT 'browser' NOT NULL"))
                 db.session.execute(text("ALTER TABLE user_preferences ADD COLUMN IF NOT EXISTS tts_voice VARCHAR(255)"))
                 db.session.execute(text("ALTER TABLE user_preferences ADD COLUMN IF NOT EXISTS tts_enabled BOOLEAN DEFAULT FALSE NOT NULL"))
                 db.session.execute(text("ALTER TABLE user_preferences ADD COLUMN IF NOT EXISTS openai_tts_model VARCHAR(50) DEFAULT 'tts-1'"))
                 db.session.execute(text("ALTER TABLE user_preferences ADD COLUMN IF NOT EXISTS openai_stt_model VARCHAR(50) DEFAULT 'whisper-1'"))
                 
                 # Step 2: Add Deepgram Key
                 db.session.execute(text("ALTER TABLE user_preferences ADD COLUMN IF NOT EXISTS deepgram_api_key VARCHAR(255)"))
                 
                 # Chat Audio Persistence
                 db.session.execute(text("ALTER TABLE messages ADD COLUMN IF NOT EXISTS audio_path VARCHAR(512)"))
                 
                 # Web Search Queries Persistence
                 db.session.execute(text("ALTER TABLE messages ADD COLUMN IF NOT EXISTS search_queries JSONB"))
                 
                 db.session.commit()
            except Exception as e:
                 # Ignore if it fails (e.g. invalid state), logs will show
                 print(f"Schema migration note: {e}")
                 pass
                 
        except SQLAlchemyError:
            pass

    return app
