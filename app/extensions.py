from flask_sqlalchemy import SQLAlchemy
from celery import Celery
from celery.signals import before_task_publish, task_prerun, setup_logging
from flask_migrate import Migrate
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from config.settings import settings

db = SQLAlchemy()
migrate = Migrate()
limiter = Limiter(
    key_func=get_remote_address,
    storage_uri=settings.REDIS_URL,
    default_limits=[]
)

def make_celery(app_name=__name__):
    celery = Celery(
        app_name,
        backend=settings.REDIS_URL,
        broker=settings.REDIS_URL,
        include=['app.tasks.processing', 'app.tasks.memory_tasks', 'app.tasks.videomix_tasks']
    )
    return celery

celery_app = make_celery("rag_worker")


@setup_logging.connect
def _configure_celery_logging(**_):
    # Prevent Celery from installing its own handlers so worker output uses
    # the same JSON formatter as the web process.
    from app.logging_config import configure_logging
    configure_logging()


# Carry the originating request id across the queue so a web request and the
# background work it triggered share one id in the logs.
@before_task_publish.connect
def _attach_request_id(headers=None, **_):
    from app.logging_config import get_request_id
    if headers is not None:
        headers["request_id"] = get_request_id()


@task_prerun.connect
def _adopt_request_id(task=None, **_):
    from app.logging_config import set_request_id
    incoming = getattr(getattr(task, "request", None), "request_id", None)
    # Tasks started without an originating request get their own id, so the
    # field is never empty.
    set_request_id(incoming if incoming and incoming != "-" else None)
