"""Migration tests get their own scratch database container, independent of
the shared session-scoped schema in tests/conftest.py, so a downgrade here
can never corrupt the schema the rest of the suite depends on.

IMPORTANT: `config/settings.py` builds its `settings` singleton from the
environment at the *first* time it (or anything importing it, like `app`)
is imported in this Python process — later `os.environ` changes do not
retroactively affect it. That means migration tests MUST run as their own
process, never mixed into the same `pytest` invocation as the main suite
(see pytest.ini's default `addopts`, which deselects the `migration` marker).
Within that isolated process, this module sets the environment before the
first import, so one Flask app/settings instance for the whole module is
correct and safe.
"""
import os

import pytest
from testcontainers.postgres import PostgresContainer


@pytest.fixture(scope="module")
def scratch_db_url():
    with PostgresContainer("pgvector/pgvector:pg16", driver="psycopg2") as postgres:
        yield postgres.get_connection_url()


@pytest.fixture(scope="module")
def scratch_app(scratch_db_url):
    """A Flask app bound to the scratch database, at whatever migration
    state the test itself drives (empty schema initially).
    """
    os.environ["DATABASE_URL"] = scratch_db_url
    os.environ.setdefault("REDIS_URL", "redis://127.0.0.1:6379/0")

    from app import create_app

    return create_app()
