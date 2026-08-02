"""Shared pytest fixtures for the backend suite.

Design constraints (see specs/004-test-suite/research.md):
- Real, disposable Postgres/Redis containers per session — never the dev DB.
- Schema built by the real Alembic chain, never db.create_all().
- `app`/`config.settings` MUST NOT be imported at module scope anywhere in
  this package: settings are built at import time, so importing early would
  bind the dev database URL instead of the test container's.
"""
import os
import socket

import pytest

pytest_plugins = ["tests.fakes.llm", "tests.fakes.embeddings"]
from testcontainers.postgres import PostgresContainer
from testcontainers.redis import RedisContainer

_ALLOWED_NETWORK_HOSTS = {"127.0.0.1", "localhost", "::1"}


@pytest.fixture(scope="session")
def postgres_url():
    with PostgresContainer("pgvector/pgvector:pg16", driver="psycopg2") as postgres:
        yield postgres.get_connection_url()


@pytest.fixture(scope="session")
def redis_url():
    with RedisContainer("redis:7-alpine") as redis:
        host = redis.get_container_host_ip()
        port = redis.get_exposed_port(6379)
        yield f"redis://{host}:{port}/0"


@pytest.fixture(scope="session")
def _app_with_migrated_schema(postgres_url, redis_url):
    """Build the Flask app against the containers and migrate it to head.

    Combined into one fixture because Flask-Migrate's env.py pulls the
    engine from `current_app` — the app must exist before `upgrade()` runs.
    `app` and `migrated_schema` below are thin views onto this single object
    so a test can depend on whichever name best expresses its intent.
    """
    os.environ["DATABASE_URL"] = postgres_url
    os.environ["REDIS_URL"] = redis_url

    from app import create_app
    from flask_migrate import upgrade
    from alembic.runtime.migration import MigrationContext

    flask_app = create_app()

    with flask_app.app_context():
        try:
            upgrade()
        except Exception as exc:  # noqa: BLE001 - re-raised with revision context
            raise RuntimeError(
                f"Migration chain failed to reach head against the test "
                f"database: {exc}"
            ) from exc

        from app.extensions import db

        with db.engine.connect() as conn:
            head_revision = MigrationContext.configure(conn).get_current_revision()

        if not head_revision:
            raise RuntimeError(
                "Migration chain applied with no resulting revision — "
                "schema is not at head."
            )

    return flask_app, head_revision


@pytest.fixture(scope="session")
def app(_app_with_migrated_schema):
    return _app_with_migrated_schema[0]


@pytest.fixture(scope="session")
def migrated_schema(_app_with_migrated_schema):
    return _app_with_migrated_schema[1]


@pytest.fixture(scope="session", autouse=True)
def assert_not_dev_database(app, postgres_url):
    """Hard guard: abort the whole run if we are not talking to the
    disposable test container. FR-002 makes this a structural requirement,
    not a matter of test-author discipline.
    """
    from urllib.parse import urlparse

    configured = urlparse(app.config["SQLALCHEMY_DATABASE_URI"])
    container = urlparse(postgres_url)

    if (configured.hostname, configured.port) != (container.hostname, container.port):
        pytest.exit(
            "Refusing to run: the app's configured database "
            f"({configured.hostname}:{configured.port}) does not match the "
            f"disposable test container ({container.hostname}:{container.port}). "
            "This guard exists to protect the persistent dev database.",
            returncode=1,
        )
    if configured.port == 5432:
        pytest.exit(
            "Refusing to run: configured database port is 5432, the default "
            "compose port. Test containers must bind a random host port.",
            returncode=1,
        )


@pytest.fixture(autouse=True)
def no_tiktoken_download(monkeypatch):
    """RAGService's token-budget guard counts tokens via tiktoken, which
    downloads its BPE file from openaipublic's blob storage on first use -
    a real network call unrelated to what any test here exercises. Stub it
    with the same rough approximation _count_tokens itself falls back to
    when tiktoken is unavailable.
    """
    import tiktoken

    class _StubEncoding:
        def encode(self, text):
            return list(range(max(1, len(text) // 4)))

    monkeypatch.setattr(tiktoken, "get_encoding", lambda name: _StubEncoding())
    monkeypatch.setattr(tiktoken, "encoding_for_model", lambda model: _StubEncoding())


@pytest.fixture(autouse=True)
def no_external_network(monkeypatch):
    """Fail loudly on any real outbound connection that isn't localhost
    (i.e. not one of our test containers). A missing fake_llm/fake_embeddings
    stub must break the test, not hang on a live provider call.
    """
    real_connect = socket.socket.connect

    def guarded_connect(self, address, *args, **kwargs):
        host = address[0] if isinstance(address, tuple) else address
        if host not in _ALLOWED_NETWORK_HOSTS:
            raise RuntimeError(
                f"Test attempted a real network connection to {host!r}. "
                "External LLM/embedding calls must be faked via the "
                "fake_llm/fake_embeddings fixtures."
            )
        return real_connect(self, address, *args, **kwargs)

    monkeypatch.setattr(socket.socket, "connect", guarded_connect)
    yield


@pytest.fixture
def db_session(app):
    """Function-scoped session bound to a rolled-back transaction.

    Standard Flask-SQLAlchemy testing pattern: swap in a session bound to a
    single connection/transaction for the test's duration, then roll back.
    """
    from app.extensions import db

    with app.app_context():
        connection = db.engine.connect()
        transaction = connection.begin()

        old_session = db.session
        db.session = db._make_scoped_session(options={"bind": connection})

        try:
            yield db.session
        finally:
            db.session.remove()
            transaction.rollback()
            connection.close()
            db.session = old_session


@pytest.fixture
def committing_db(app):
    """Real commits — for tests asserting commit-time behavior (e.g. the
    search_vector trigger). Truncates the tables it touched at teardown.

    Use `session.info["truncate"] = {"chunks", "documents"}` (or similar) to
    tell the fixture which tables need cleanup, since it cannot know in
    advance which tables a given test will write to.
    """
    from app.extensions import db

    with app.app_context():
        db.session.info["truncate"] = set()
        try:
            yield db.session
        finally:
            tables = db.session.info.get("truncate", set())
            if tables:
                db.session.execute(
                    db.text(f"TRUNCATE TABLE {', '.join(tables)} CASCADE")
                )
                db.session.commit()
            db.session.remove()


@pytest.fixture
def client(app, db_session):
    return app.test_client()


@pytest.fixture
def tmp_uploads(tmp_path, monkeypatch):
    """Redirect settings.UPLOAD_FOLDER to a per-test temp directory so no
    test writes into the real uploads/ tree. app/api/documents.py reads
    settings.UPLOAD_FOLDER directly (not app.config), so the settings
    singleton is what must be patched.
    """
    from config.settings import settings

    upload_dir = tmp_path / "uploads"
    upload_dir.mkdir()
    monkeypatch.setattr(settings, "UPLOAD_FOLDER", str(upload_dir))
    return upload_dir
