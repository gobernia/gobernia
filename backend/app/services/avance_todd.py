"""«Avance contado a Todd»: cuando alguien no tiene un documento para subir, le cuenta a Todd qué
hicieron y Todd lo guarda en la tarea como un PDF. Queda como evidencia más: aparece en la lista
de documentos, se puede descargar o borrar, y el Auditor lo revisa igual que cualquier documento
(si es concreto y creíble, puede validarlo; decisión del dueño de Gobernia, 25 nov 2026)."""
import uuid
from datetime import datetime, timezone

import anyio

from app.models.action_plan import ActionTask
from app.models.evidence import Evidence
from app.services.documents.storage import generate_storage_key, upload_to_storage
from app.services.evidencia_revision import marcar_revisando
from app.services.ai.avance_herramienta import REGISTRAR_AVANCE_TOOL, datos_del_avance  # noqa: F401
from app.services.pdf.avance_pdf import build_avance_pdf, fecha_larga

PREFIJO = "Avance contado a Todd"

async def registrar_avance(db, task: ActionTask, datos: dict, contado_por: str) -> tuple[str, str]:
    """Crea el PDF, lo sube y lo agrega a la tarea como evidencia; deja la tarea «revisando».
    Devuelve (revision_id, nombre del archivo). Quien llama hace commit y lanza la revisión."""
    ahora = datetime.now(timezone.utc)
    pdf = await anyio.to_thread.run_sync(lambda: build_avance_pdf(task.title, contado_por, ahora, datos))
    ev_id = uuid.uuid4()
    filename = f"{PREFIJO} - {fecha_larga(ahora)}.pdf"
    s3_key = generate_storage_key(task.id, ev_id, filename)
    await upload_to_storage(pdf, s3_key)
    db.add(Evidence(id=ev_id, action_task_id=task.id, filename=filename, s3_key=s3_key,
                    content_type="application/pdf", size_bytes=len(pdf)))
    if task.status == "pendiente":
        task.status = "en_progreso"
    return marcar_revisando(task), filename
