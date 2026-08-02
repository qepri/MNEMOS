import logging
import os
import time
import threading
from flask import Flask, jsonify
from sqlalchemy import text
from config.settings import settings
from app.extensions import db, migrate, celery_app, limiter

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)

def create_app():
    app = Flask(__name__)

    # Disable Flask's strict slashes to avoid redirect issues with nginx proxy
    app.url_map.strict_slashes = False

    # Configure app from settings
    app.config["SQLALCHEMY_DATABASE_URI"] = settings.DATABASE_URL
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["SECRET_KEY"] = settings.SECRET_KEY
    app.config["MAX_CONTENT_LENGTH"] = settings.MAX_CONTENT_LENGTH
    app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
        "pool_size": 20,
        "pool_recycle": 1800,
        "pool_pre_ping": True,
    }
    app.config.from_prefixed_env()

    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)
    limiter.init_app(app)
    
    # Configure Celery
    celery_app.conf.update(app.config)

    # Register Blueprints
    from app.api.documents import bp as documents_bp
    from app.api.chat import bp as chat_bp
    from app.api.conversations import bp as conversations_bp
    from app.api.settings import bp as settings_bp
    from app.api.connections import bp as connections_bp
    from app.api.collections import bp as collections_bp
    from app.api.docs import bp as docs_bp

    app.register_blueprint(documents_bp)
    app.register_blueprint(collections_bp)
    app.register_blueprint(chat_bp)
    app.register_blueprint(conversations_bp)
    app.register_blueprint(settings_bp, url_prefix='/api/settings') # Changed: Added url_prefix
    app.register_blueprint(connections_bp)
    app.register_blueprint(docs_bp)
    
    from app.api.memory import bp as memory_bp
    app.register_blueprint(memory_bp, url_prefix='/api/memory')

    from app.api.voice import voice_bp
    app.register_blueprint(voice_bp, url_prefix='/api/voice')

    from app.api.reasoning import bp as reasoning_bp
    app.register_blueprint(reasoning_bp)

    from app.api.wiki import bp as wiki_bp
    app.register_blueprint(wiki_bp)
    from app.api.videomix import bp as videomix_bp
    app.register_blueprint(videomix_bp)

    # CLI commands
    from app import cli as _cli
    _cli.register(app)

    _health_cache: dict = {"result": None, "at": 0.0}
    _health_lock = threading.Lock()

    @app.get('/api/health')
    def health():
        now = time.monotonic()
        with _health_lock:
            cached = _health_cache["result"]
            if cached is not None and now - _health_cache["at"] < 5.0:
                return jsonify(cached[0]), cached[1]

        checks = {"db": False, "redis": False}
        try:
            db.session.execute(text("SELECT 1"))
            checks["db"] = True
        except Exception:
            pass
        try:
            celery_app.backend.client.ping()
            checks["redis"] = True
        except Exception:
            pass
        ok = all(checks.values())
        payload = {"status": "ok" if ok else "degraded", **checks}
        code = 200 if ok else 503
        with _health_lock:
            _health_cache["result"] = (payload, code)
            _health_cache["at"] = now
        return jsonify(payload), code

    from sqlalchemy.exc import SQLAlchemyError
    # Import models to ensure they are registered with SQLAlchemy
    with app.app_context():
        try:
            # Ensure pgvector extension exists
            db.session.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            db.session.commit()
        except SQLAlchemyError:
            db.session.rollback()
            pass

        try:
            db.session.execute(text(
                "ALTER TABLE user_preferences ADD COLUMN IF NOT EXISTS retrieval_top_k INTEGER NOT NULL DEFAULT 10"
            ))
            db.session.commit()
        except SQLAlchemyError:
            db.session.rollback()
            pass

        try:
            db.session.execute(text(
                "ALTER TABLE user_preferences ADD COLUMN IF NOT EXISTS hypergraph_llm_provider VARCHAR(50) DEFAULT ''"
            ))
            db.session.execute(text(
                "ALTER TABLE user_preferences ADD COLUMN IF NOT EXISTS hypergraph_llm_model VARCHAR(255) DEFAULT ''"
            ))
            db.session.commit()
        except SQLAlchemyError:
            db.session.rollback()
            pass

        try:
            db.session.execute(text(
                "ALTER TABLE documents ADD COLUMN IF NOT EXISTS embedding_model_used VARCHAR(255)"
            ))
            db.session.commit()
        except SQLAlchemyError:
            db.session.rollback()
            pass

        # Pre-warm the embedding model in background so first wiki fuzzy lookup is fast
        try:
            def _warm_embedder():
                from app.services.embedder import EmbedderService
                logger.info("Pre-warming embedding model...")
                EmbedderService.get_instance()
                logger.info("Embedding model ready.")
            t = threading.Thread(target=_warm_embedder, daemon=True)
            t.start()
        except Exception as e:
            logger.warning(f"Embedding model pre-warm failed (will load on demand): {e}")

        try:
            # Import models so SQLAlchemy knows about them
            from app import models

            # Create all tables based on the model definitions
            # This is idempotent - it won't recreate existing tables
            db.create_all()
            logger.info("Database tables created successfully")

            # Migrate existing collection_id FK data into junction table
            from sqlalchemy import text as sql_text
            db.session.execute(sql_text("""
                INSERT INTO collection_documents (collection_id, document_id)
                SELECT collection_id, id FROM documents
                WHERE collection_id IS NOT NULL
                ON CONFLICT (collection_id, document_id) DO NOTHING
            """))
            db.session.commit()
            logger.info("Legacy collection_id data migrated to collection_documents junction")

        except SQLAlchemyError as e:
            db.session.rollback()
            logger.warning(f"Database initialization: {e}")

        # Create VideoMix output directory
        try:
            videomix_output_dir = os.path.join(settings.UPLOAD_FOLDER, 'videomix_output')
            os.makedirs(videomix_output_dir, exist_ok=True)
            logger.info(f"VideoMix output directory ready: {videomix_output_dir}")
        except Exception as e:
            logger.warning(f"Could not create VideoMix output directory: {e}")

    return app
