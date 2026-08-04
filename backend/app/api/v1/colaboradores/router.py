"""Escritorio del responsable por ENLACE MÁGICO.
El dueño (autenticado) genera/copia un enlace /t/{token}; el responsable ve SOLO sus
tareas sin login, cada una con la explicación de Todd (generada bajo demanda)."""
import uuid

import anyio
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.core.dependencies import get_current_user_id, get_db
from app.models.action_plan import ActionTask
from app.models.annual_plan import AnnualPlan, MonthlyPlan, Objective
from app.models.colaborador import Colaborador
from app.models.onboarding_session import OnboardingSession
from app.schemas.colaborador import (
    ColaboradorLinkIn,
    ColaboradorLinkOut,
    EscritorioOut,
    TareaColabOut,
)
from app.services.ai.task_explainer import generate_explicacion

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
    # La tarea debe ser de este colaborador (mismo owner_email + user_id del dueño).
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
    task, objetivo = fila
    if task.explicacion:
        return task.explicacion
    empresa = await _empresa_nombre(col.user_id, db) or ""
    data = await anyio.to_thread.run_sync(
        lambda: generate_explicacion(task.title, objetivo or "", empresa, task.kpi_ref))
    task.explicacion = data
    flag_modified(task, "explicacion")
    await db.commit()
    return data
