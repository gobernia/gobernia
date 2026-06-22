from celery import Celery
from app.core.config import settings

celery_app = Celery(
    "gobernia",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=["app.tasks.document_tasks", "app.tasks.annual_plan_tasks",
             "app.tasks.diagnostico_tasks", "app.tasks.foda_tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="America/Mexico_City",
    task_track_started=True,
)
