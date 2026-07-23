from celery import Celery
from app.core.config import settings

celery_app = Celery(
    "gobernia",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=["app.tasks.document_tasks", "app.tasks.annual_plan_tasks",
             "app.tasks.diagnostico_tasks", "app.tasks.foda_tasks", "app.tasks.perspectivas_tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="America/Mexico_City",
    task_track_started=True,
    # Reintenta la conexión al broker en el arranque (comportamiento explícito, Celery 6+).
    broker_connection_retry_on_startup=True,
    # Un worker atascado retiene UNA tarea, no un lote: acota el daño de un nodo colgado.
    worker_prefetch_multiplier=1,
    # LÍMITE DE TIEMPO: ninguna tarea corre para siempre. A los 25 min se lanza
    # SoftTimeLimitExceeded (la tarea lo atrapa y marca 'failed' → el cliente ve un error,
    # no un spinner de horas). A los 30 min, kill duro de respaldo.
    task_soft_time_limit=1500,
    task_time_limit=1800,
)
