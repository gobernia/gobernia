"""Escritorio del responsable por ENLACE MÁGICO.
El dueño (autenticado) genera/copia un enlace /t/{token}; el responsable ve SOLO sus
tareas sin login, cada una con la explicación de Todd (generada bajo demanda). Desde ahí también
sube la evidencia de SUS tareas: el Auditor la revisa igual que si la subiera el dueño."""
import uuid

import anyio
from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.core.dependencies import get_current_user_id, get_db
from app.models.action_plan import ActionTask
from app.models.annual_plan import AnnualPlan, MonthlyPlan, Objective
from app.models.colaborador import Colaborador
from app.models.evidence import Evidence
from app.models.onboarding_session import OnboardingSession
from app.schemas.colaborador import (
    ColaboradorLinkIn,
    ColaboradorLinkOut,
    EscritorioOut,
    TareaColabOut,
    ToddChatOut,
    ToddMsgIn,
    ToddReplyOut,
)
from app.services.ai.task_explainer import generate_explicacion
from app.services.ai.todd_responsable import run_todd_responsable
from app.services.documents.storage import generate_storage_key, upload_to_storage
from app.services.evidencia_revision import marcar_revisando, revisar_evidencia_tarea, validacion_visible

# Máximo de mensajes que guardamos en el historial (para no crecer sin fin).
_MAX_CHAT = 40

router = APIRouter()


async def _empresa_nombre(user_id: str, db: AsyncSession) -> str | None:
    onb = (await db.execute(
        select(OnboardingSession).where(OnboardingSession.user_id == user_id)
        .order_by(OnboardingSession.created_at.desc())
    )).scalars().first()
    return (((onb.memory_buffer if onb else {}) or {}).get("company") or {}).get("name") or None


async def _tareas_del_colaborador(col: Colaborador, db: AsyncSession):
    """Tareas cuyo owner_email == col.email (case-insensitive) y del plan del dueño."""
    res = await db.execute(
        select(ActionTask, Objective.title)
        .join(Objective, ActionTask.objective_id == Objective.id)
        .join(MonthlyPlan, Objective.monthly_plan_id == MonthlyPlan.id)
        .join(AnnualPlan, MonthlyPlan.annual_plan_id == AnnualPlan.id)
        .where(
            AnnualPlan.user_id == col.user_id,
            func.lower(ActionTask.owner_email) == col.email.lower(),
        )
        .order_by(ActionTask.due_date.asc().nullslast(), ActionTask.order_index.asc())
    )
    return res.all()


# ── POST /colaboradores/link (dueño, autenticado) ────────────────────────────
@router.post("/colaboradores/link", response_model=ColaboradorLinkOut)
async def crear_o_obtener_link(
    body: ColaboradorLinkIn,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    email = body.email.strip()
    if not email:
        raise HTTPException(status_code=400, detail="El correo es obligatorio.")
    res = await db.execute(
        select(Colaborador).where(
            Colaborador.user_id == user_id,
            func.lower(Colaborador.email) == email.lower(),
        )
    )
    col = res.scalar_one_or_none()
    if col is None:
        col = Colaborador(user_id=user_id, email=email, nombre=body.nombre, token=uuid.uuid4().hex)
        db.add(col)
    else:
        if body.nombre is not None:
            col.nombre = body.nombre
    await db.commit()
    await db.refresh(col)
    return ColaboradorLinkOut(token=col.token)


async def _tarea_del_colaborador(col: Colaborador, task_id: uuid.UUID, db: AsyncSession):
    """(tarea, título del objetivo) si la tarea es de este colaborador (mismo owner_email y del
    plan del mismo dueño). Si no, 404: con un enlace solo se tocan las tareas propias."""
    res = await db.execute(
        select(ActionTask, Objective.title)
        .join(Objective, ActionTask.objective_id == Objective.id)
        .join(MonthlyPlan, Objective.monthly_plan_id == MonthlyPlan.id)
        .join(AnnualPlan, MonthlyPlan.annual_plan_id == AnnualPlan.id)
        .where(
            ActionTask.id == task_id,
            AnnualPlan.user_id == col.user_id,
            func.lower(ActionTask.owner_email) == col.email.lower(),
        )
    )
    fila = res.first()
    if fila is None:
        raise HTTPException(status_code=404, detail="Tarea no encontrada.")
    return fila


async def _colaborador_por_token(token: str, db: AsyncSession) -> Colaborador:
    res = await db.execute(select(Colaborador).where(Colaborador.token == token))
    col = res.scalar_one_or_none()
    if col is None:
        raise HTTPException(status_code=404, detail="Enlace no encontrado.")
    return col


# ── GET /t/{token} (público) ─────────────────────────────────────────────────
@router.get("/t/{token}", response_model=EscritorioOut)
async def get_escritorio(token: str, db: AsyncSession = Depends(get_db)):
    col = await _colaborador_por_token(token, db)
    empresa = await _empresa_nombre(col.user_id, db)
    filas = await _tareas_del_colaborador(col, db)
    ids = [t.id for (t, _) in filas]
    conteo: dict = {}
    if ids:
        conteo = dict((await db.execute(
            select(Evidence.action_task_id, func.count(Evidence.id))
            .where(Evidence.action_task_id.in_(ids)).group_by(Evidence.action_task_id)
        )).all())
    tareas = [
        TareaColabOut(
            id=str(t.id),
            title=t.title,
            description=t.description,
            status=t.status,
            due_date=t.due_date.isoformat() if t.due_date else None,
            objetivo=obj_title,
            explicacion=t.explicacion,
            tiene_explicacion=bool(t.explicacion),
            evidencias=int(conteo.get(t.id, 0)),
            validacion=validacion_visible(t.validacion),
        )
        for (t, obj_title) in filas
    ]
    return EscritorioOut(nombre=col.nombre, empresa=empresa, tareas=tareas)


# ── POST /t/{token}/tareas/{task_id}/explicar (público) ──────────────────────
@router.post("/t/{token}/tareas/{task_id}/explicar")
async def explicar_tarea_colaborador(
    token: str,
    task_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    col = await _colaborador_por_token(token, db)
    task, objetivo = await _tarea_del_colaborador(col, task_id, db)
    if task.explicacion:
        return task.explicacion
    empresa = await _empresa_nombre(col.user_id, db) or ""
    data = await anyio.to_thread.run_sync(
        lambda: generate_explicacion(task.title, objetivo or "", empresa, task.kpi_ref))
    task.explicacion = data
    flag_modified(task, "explicacion")
    await db.commit()
    return data


# ── POST /t/{token}/tareas/{task_id}/evidencia (público) ─────────────────────
@router.post("/t/{token}/tareas/{task_id}/evidencia")
async def subir_evidencia_colaborador(
    token: str,
    task_id: uuid.UUID,
    background: BackgroundTasks,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    """El responsable sube la evidencia de SU tarea. Mismo trato que la subida del dueño: mismos
    tipos y tamaño, la tarea pasa a 'en progreso' y el Auditor la lee al momento. A Todd (del
    dueño) le llega el aviso diciendo quién la subió."""
    from app.api.v1.evidence.router import _validate_file

    col = await _colaborador_por_token(token, db)
    task, _ = await _tarea_del_colaborador(col, task_id, db)
    content = await file.read()
    _validate_file(file.filename or "", content)

    ev_id = uuid.uuid4()
    filename = file.filename or f"evidencia_{ev_id}"
    s3_key = generate_storage_key(task.id, ev_id, filename)
    await upload_to_storage(content, s3_key)
    db.add(Evidence(
        id=ev_id, action_task_id=task.id, filename=filename, s3_key=s3_key,
        content_type=file.content_type or "application/octet-stream", size_bytes=len(content),
    ))
    if task.status == "pendiente":
        task.status = "en_progreso"
    revision_id = marcar_revisando(task)
    await db.commit()
    background.add_task(revisar_evidencia_tarea, task.id, col.user_id, revision_id,
                        subido_por=(col.nombre or col.email))
    return {"ok": True, "filename": filename}


# ── GET /t/{token}/todd (público) — historial del chat ───────────────────────
@router.get("/t/{token}/todd", response_model=ToddChatOut)
async def get_todd_chat(token: str, db: AsyncSession = Depends(get_db)):
    col = await _colaborador_por_token(token, db)
    return ToddChatOut(mensajes=col.chat or [])


# ── POST /t/{token}/todd (público) — un turno del chat ───────────────────────
@router.post("/t/{token}/todd", response_model=ToddReplyOut)
async def post_todd_chat(
    token: str,
    body: ToddMsgIn,
    db: AsyncSession = Depends(get_db),
):
    col = await _colaborador_por_token(token, db)
    mensaje = (body.mensaje or "").strip()
    if not mensaje:
        raise HTTPException(status_code=400, detail="El mensaje es obligatorio.")

    empresa = await _empresa_nombre(col.user_id, db)
    filas = await _tareas_del_colaborador(col, db)
    ids = [t.id for (t, _) in filas]
    conteo: dict = {}
    if ids:
        conteo = dict((await db.execute(
            select(Evidence.action_task_id, func.count(Evidence.id))
            .where(Evidence.action_task_id.in_(ids)).group_by(Evidence.action_task_id)
        )).all())
    tareas = [
        {
            "title": t.title,
            "description": t.description,
            "status": t.status,
            "objetivo": obj_title,
            "explicacion": t.explicacion,
            "evidencias": int(conteo.get(t.id, 0)),
            "validacion": validacion_visible(t.validacion),
        }
        for (t, obj_title) in filas
    ]

    historial = list(col.chat or [])
    mensajes = historial + [{"role": "user", "content": mensaje}]
    reply = await anyio.to_thread.run_sync(
        lambda: run_todd_responsable(mensajes, col.nombre, empresa, tareas)
    )

    nuevo = (mensajes + [{"role": "todd", "content": reply}])[-_MAX_CHAT:]
    col.chat = nuevo
    flag_modified(col, "chat")
    await db.commit()
    return ToddReplyOut(reply=reply, mensajes=nuevo)
