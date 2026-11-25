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
    visible = {"estado": v.get("estado"), "motivo": v.get("motivo")}
    for campo in ("documento", "otro_documento", "cubre", "falta", "alternativas", "origen"):
        if v.get(campo):
            visible[campo] = v[campo]
    return visible


async def revisar_evidencia_tarea(task_id: uuid.UUID, user_id: str, revision_id: str) -> None:
    # Import diferido: el router de sesiones es pesado y a su vez importa servicios de IA.
    from app.api.v1.board_sessions.router import _validar_evidencias_del_periodo

    archivo = "tu documento"
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
            if evs:
                archivo = evs[0].filename  # el que se acaba de subir
            candidato = {
                "task_id": str(task.id),
                "title": task.title,
                "status": task.status,
                "required_doc": task.required_doc,
                "description": task.description,
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
            **{k: veredicto[k] for k in ("estado", "documento", "otro_documento", "cubre", "falta", "alternativas")
               if k in veredicto},
            "motivo": veredicto.get("motivo", ""),
            "validated_at": datetime.now(timezone.utc).isoformat(),
            "origen": "al_subir",
        }
        flag_modified(task, "validacion")
        tarea = task.title
        await db.commit()  # el veredicto queda guardado antes de avisar
        await _avisar_con_todd(db, user_id, str(task_id), tarea, archivo, veredicto)


async def _avisar_con_todd(db, user_id: str, task_id: str, tarea: str, archivo: str,
                           veredicto: dict) -> None:
    """Deja en el chat de Todd lo que encontró el Auditor (qué está, qué falta, qué más sirve).
    Si falla, el veredicto ya está guardado: el aviso de Todd nunca tumba la revisión."""
    # Import diferido: el servicio de Todd importa este módulo.
    from app.api.v1.todd_secretario.service import TODD_SECRETARIO_AGENT, get_anchor_board_session_id
    from app.models.chat_message import ChatMessage
    from app.services.evidencia_todd import mensaje_de_todd

    try:
        anchor_id = await get_anchor_board_session_id(user_id, db)
        if anchor_id is None:
            return  # sin sesión de Consejo el chat de Todd no tiene dónde guardarse
        db.add(ChatMessage(
            board_session_id=anchor_id, user_id=user_id, role="assistant", agent=TODD_SECRETARIO_AGENT,
            content=mensaje_de_todd(veredicto, tarea, archivo),
            message_metadata={"revision": {
                "task_id": task_id, "tarea": tarea, "archivo": archivo, "estado": veredicto.get("estado"),
                "documento": veredicto.get("documento") or "",
                "otro_documento": bool(veredicto.get("otro_documento")),
            }},
        ))
        await db.commit()
    except Exception:
        _log.exception("no se pudo dejar el aviso de Todd para la tarea %s", task_id)
        await db.rollback()
