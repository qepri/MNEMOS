"""Flask CLI commands. Registered from create_app()."""
import click
from flask.cli import with_appcontext


def register(app):
    @app.cli.command("reembed-all")
    @click.option("--sync", is_flag=True, help="Run in-process instead of via Celery worker.")
    @with_appcontext
    def reembed_all_cmd(sync):
        """Re-embed all chunks and concepts with the current EMBEDDING_MODEL."""
        from app.tasks.reembed import reembed_all
        if sync:
            click.echo("Running re-embed synchronously (no Celery)...")
            # Build a minimal stand-in for `self` so update_state calls don't crash
            class _Self:
                def update_state(self, **kwargs): pass
            result = reembed_all.run.__wrapped__(_Self()) if hasattr(reembed_all.run, "__wrapped__") else reembed_all(_Self())
            click.echo(f"Done: {result}")
        else:
            task = reembed_all.delay()
            click.echo(f"Enqueued. Task ID: {task.id}")
            click.echo("Poll status: GET /api/settings/reembed/status/<task_id>")
