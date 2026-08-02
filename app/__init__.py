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

    # Import models so SQLAlchemy (and Alembic autogenerate) know about them.
    # Schema is owned entirely by migrations: `flask db upgrade`, run from
    # entrypoint.sh when RUN_MIGRATIONS=true. Startup performs no DDL.
    from app import models  # noqa: F401

    # Pre-warming loads the embedding model into VRAM. It must not happen in
    # create_app(), which runs in every gunicorn worker and in Celery.
    if os.getenv("PREWARM_EMBEDDER", "false").lower() == "true":
        def _warm_embedder():
            from app.services.embedder import EmbedderService
            logger.info("Pre-warming embedding model...")
            EmbedderService.get_instance()
            logger.info("Embedding model ready.")
        threading.Thread(target=_warm_embedder, daemon=True).start()

    try:
        os.makedirs(os.path.join(settings.UPLOAD_FOLDER, 'videomix_output'), exist_ok=True)
    except OSError as e:
        logger.warning(f"Could not create VideoMix output directory: {e}")

    return app
