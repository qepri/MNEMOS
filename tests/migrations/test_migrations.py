"""Migration chain round-trip: baseline -> head applies in order, and the
chain reverses without error. Run in isolation: `pytest -m migration`
(see conftest.py for why this must be its own process).
"""
import pytest

pytestmark = pytest.mark.migration


def test_upgrade_reaches_head_in_order(scratch_app):
    from flask_migrate import upgrade
    from alembic.runtime.migration import MigrationContext
    from app.extensions import db

    with scratch_app.app_context():
        try:
            upgrade()
        except Exception as exc:  # noqa: BLE001
            pytest.fail(f"Migration chain failed to reach head: {exc}")

        with db.engine.connect() as conn:
            head = MigrationContext.configure(conn).get_current_revision()
        assert head, "Migration chain applied but produced no head revision"


def test_downgrade_round_trip_does_not_error(scratch_app):
    from flask_migrate import upgrade, downgrade

    with scratch_app.app_context():
        upgrade()  # empty -> head (idempotent if already there from another test)

        try:
            downgrade(revision="base")
        except Exception as exc:  # noqa: BLE001
            pytest.fail(f"Downgrade to base failed: {exc}")

        # Re-upgrade so subsequent tests in this module start from a known
        # (head) state regardless of execution order.
        upgrade()


def test_baseline_plus_fts_revisions_create_search_vector_trigger(scratch_app):
    """Regression guard for the historical bug where chunks.search_vector
    was always NULL: confirms the update_chunk_search_vector trigger exists
    once a005/a006 are applied on top of the baseline (CLAUDE.md Database
    section).
    """
    from flask_migrate import upgrade
    from app.extensions import db

    with scratch_app.app_context():
        upgrade()  # ensure head

        result = db.session.execute(
            db.text(
                "SELECT 1 FROM pg_trigger WHERE tgname = 'update_chunk_search_vector'"
            )
        ).fetchone()
        assert result is not None, "update_chunk_search_vector trigger is missing at head"
