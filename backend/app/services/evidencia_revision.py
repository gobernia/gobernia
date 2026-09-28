"""Revisión inmediata de la evidencia de UNA tarea: el Auditor lee el documento en cuanto se sube,
en vez de esperar a que se sesione el mes. Corre en segundo plano después de responder el upload.

Mientras corre, la tarea queda con validacion.estado = "revisando" y un `revision_id`. Solo la
revisión más reciente escribe su veredicto (si el dueño sube dos archivos seguidos, gana la última).
"""
import logging
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm.attributes import flag_modified

from app.db.session import AsyncSessionLocal
from app.models.action_plan import ActionTask
from app.models.evidence import Evidence
from app.models.onboarding_session import OnboardingSession

_log = logging.getLogger(__name__)

# Una revisión que lleva más que esto en "revisando" se da por perdida (p. ej. reinicio del servidor).
REVISION_EXPIRA = timedelta(minutes=10)


def marcar_revisando(task: ActionTask) -> str:
    """Pone la tarea en 'revisando' y devuelve el id de esta revisión."""
    rid = uuid.uuid4().hex
    task.validacion = {
        "estado": "revisando",
        "motivo": "",
        "desde": datetime.now(timezone.utc).isoformat(),
        "revision_id": rid,
    }
    flag_modified(task, "validacion")
    return rid


def validacion_visible(v: dict | None) -> dict | None:
    """El veredicto que ve el dueño. Una revisión colgada se muestra como no revisada."""
    if not v:
        return None
    if v.get("estado") == "revisando":
        try:
            desde = datetime.fromisoformat(v.get("desde") or "")
        except ValueError:
            desde = None
        if desde is None or datetime.now(timezone.utc) - desde > REVISION_EXPIRA:
            return {"estado": "sin_revisar",
                    "motivo": "La revisión no terminó. Vuelve a subir el documento o sesiona el mes."}
    return {"estado": v.get("estado"), "motivo": v.get("motivo")}


async def revisar_evidencia_tarea(task_id: uuid.UUID, user_id: str, revision_id: str) -> None:
    # Import diferido: el router de sesiones es pesado y a su vez importa servicios de IA.
    from app.api.v1.board_sessions.router import _validar_evidencias_del_periodo

    try:
        async with AsyncSessionLocal() as db:
            task = await db.get(ActionTask, task_id)
            if task is None:
                return
            evs = (await db.execute(
                select(Evidence).where(Evidence.action_task_id == task_id)
                .order_by(Evidence.created_at.desc())
            )).scalars().all()
            onb = (await db.execute(
                select(OnboardingSession).where(OnboardingSession.user_id == user_id)
                .order_by(OnboardingSession.created_at.desc())
            )).scalars().first()
            memory_buffer = (onb.memory_buffer if onb else {}) or {}
            candidato = {
                "task_id": str(task.id),
                "title": task.title,
                "status": task.status,
                "evidences": [{"s3_key": e.s3_key, "filename": e.filename, "size_bytes": e.size_bytes}
                              for e in evs],
            }
        resultados = await _validar_evidencias_del_periodo([candidato], memory_buffer)
        veredicto = resultados.get(str(task_id)) or {
            "estado": "sin_revisar", "motivo": "No se pudo revisar el documento."}
    except Exception:
        _log.exception("la revisión inmediata de la evidencia de %s falló", task_id)
        veredicto = {"estado": "sin_revisar", "motivo": "No se pudo revisar el documento."}

    async with AsyncSessionLocal() as db:
        task = await db.get(ActionTask, task_id)
        if task is None or (task.validacion or {}).get("revision_id") != revision_id:
            return  # llegó una revisión más nueva (u otro veredicto): no se pisa
        task.validacion = {
            "estado": veredicto["estado"],
            "motivo": veredicto.get("motivo", ""),
            "validated_at": datetime.now(timezone.utc).isoformat(),
            "origen": "al_subir",
        }
        flag_modified(task, "validacion")
        await db.commit()
