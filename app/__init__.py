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
    from app.api.ollama_manage import bp as ollama_manage_bp # Changed: Import ollama_manage_bp
    
    app.register_blueprint(documents_bp)
    app.register_blueprint(chat_bp)
    app.register_blueprint(web_bp)
    app.register_blueprint(conversations_bp)
    app.register_blueprint(settings_bp, url_prefix='/api/settings') # Changed: Added url_prefix
    app.register_blueprint(ollama_manage_bp, url_prefix='/api/settings/ollama') # Changed: Register ollama_manage_bp
    
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
        except SQLAlchemyError:
            pass

    return app
