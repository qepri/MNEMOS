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

    from app.api.reasoning import bp as reasoning_bp
    app.register_blueprint(reasoning_bp)
    
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
            # Import models so SQLAlchemy knows about them
            from app import models

            # Create all tables based on the model definitions
            # This is idempotent - it won't recreate existing tables
            db.create_all()
            print("Database tables created successfully")

        except SQLAlchemyError as e:
            print(f"Database initialization note: {e}")
            pass

    return app
