from flask_sqlalchemy import SQLAlchemy
from celery import Celery
from flask_migrate import Migrate
from config.settings import settings

db = SQLAlchemy()
migrate = Migrate()

def make_celery(app_name=__name__):
    celery = Celery(
        app_name,
        backend=settings.REDIS_URL,
        broker=settings.REDIS_URL,
        include=['app.tasks.processing', 'app.tasks.memory_tasks']
    )
    return celery

celery_app = make_celery("rag_worker")
