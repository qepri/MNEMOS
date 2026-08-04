import logging
import os
import time
import threading
from flask import Flask, jsonify
from sqlalchemy import text
from config.settings import LLMProvider, settings
from app.extensions import db, migrate, celery_app, limiter

from app.logging_config import configure_logging

configure_logging()
logger = logging.getLogger(__name__)


def _migration_status() -> dict:
    """Compare the DB's Alembic revision against the migration scripts' head."""
    try:
        from alembic.script import ScriptDirectory
        from alembic.runtime.migration import MigrationContext
        from flask_migrate import current_app as _fm_app  # noqa: F401
        from flask import current_app

        config = current_app.extensions['migrate'].migrate.get_config()
        script = ScriptDirectory.from_config(config)
        head = script.get_current_head()

        with db.engine.connect() as conn:
            db_rev = MigrationContext.configure(conn).get_current_revision()

        return {"ok": db_rev == head, "current": db_rev, "head": head}
    except Exception as e:
        return {"ok": False, "detail": str(e)}


def _llamacpp_status() -> dict:
    """Probe llama.cpp with a short timeout; it must never hang readiness."""
    import requests
    base = settings.LLAMACPP_BASE_URL.rstrip('/')
    if base.endswith('/v1'):
        base = base[:-3].rstrip('/')
    try:
        r = requests.get(f"{base}/health", timeout=2)
        return {"ok": r.status_code == 200}
    except Exception as e:
        return {"ok": False, "detail": type(e).__name__}


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

    from app import logging_config
    logging_config.init_app(app)
    
    # Configure Celery
    celery_app.conf.update(app.config)

    # Register Blueprints
    from app.api.documents import bp as documents_bp
    from app.api.chat import bp as chat_bp
    from app.api.conversations import bp as conversations_bp
    from app.api.settings import bp as settings_bp
    # Imported for their route-registration side effects on settings_bp.
    from app.api import settings_models, settings_downloads  # noqa: F401
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

    _ready_cache: dict = {"result": None, "at": 0.0}
    _ready_lock = threading.Lock()

    @app.get('/api/ready')
    def ready():
        """Readiness: liveness plus migrations applied, and llama.cpp reachable
        when this deployment actually runs it.

        Distinct from /api/health on purpose. A cold llama.cpp start can take
        minutes, which is a normal transient state - the process is alive, so
        liveness stays 200 while readiness reports 503.

        In slim mode (any LLM provider other than llamacpp) the llamacpp key is
        omitted from the payload entirely rather than reported as ok - saying a
        service is healthy when it was never probed would mislead an operator.
        """
        now = time.monotonic()
        with _ready_lock:
            cached = _ready_cache["result"]
            if cached is not None and now - _ready_cache["at"] < 5.0:
                return jsonify(cached[0]), cached[1]

        payload: dict = {}

        try:
            db.session.execute(text("SELECT 1"))
            payload["db"] = True
        except Exception:
            db.session.rollback()
            payload["db"] = False

        try:
            celery_app.backend.client.ping()
            payload["redis"] = True
        except Exception:
            payload["redis"] = False

        payload["migrations"] = _migration_status()

        # Slim deployments never start the llamacpp container, so probing it
        # would pin readiness at 503 forever. Keyed on settings (a deploy-time
        # value that tracks which containers compose started) rather than
        # UserPreferences, which a user can flip at runtime without changing
        # any infrastructure - readiness would flap for no reason.
        uses_llamacpp = settings.LLM_PROVIDER == LLMProvider.LLAMACPP
        if uses_llamacpp:
            payload["llamacpp"] = _llamacpp_status()

        ok = (
            payload["db"]
            and payload["redis"]
            and payload["migrations"]["ok"]
            and (not uses_llamacpp or payload["llamacpp"]["ok"])
        )
        payload["status"] = "ready" if ok else "not_ready"
        code = 200 if ok else 503

        with _ready_lock:
            _ready_cache["result"] = (payload, code)
            _ready_cache["at"] = now
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
