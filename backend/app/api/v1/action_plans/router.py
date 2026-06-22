"""
Action Plans — endpoints CRUD + generación con IA.
- POST /board-sessions/{id}/plan         → genera plan desde análisis
- GET  /board-sessions/{id}/plan         → obtiene el plan con sus tareas
- POST /plans/{id}/tasks                 → crea una tarea manual
- PATCH /tasks/{id}                      → actualiza cualquier campo (status, title, etc.)
- DELETE /tasks/{id}                     → borra tarea
"""
import uuid
from datetime import datetime

import anyio
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.core.dependencies import get_current_user_id, get_db
from app.models.action_plan import ActionPlan, ActionTask
from app.models.evidence import Evidence
from app.models.annual_plan import AnnualPlan, MonthlyPlan, Objective
from app.models.board_session import BoardSession
from app.models.onboarding_session import OnboardingSession
from app.schemas.action_plan import (
    ActionPlanOut,
    ActionTaskCreate,
    ActionTaskOut,
    ActionTaskUpdate,
    GeneratePlanResponse,
)
from app.services.ai.plan_generator import generate_action_plan
from app.services.ai.task_explainer import generate_explicacion

router = APIRouter()

_MONTHS = [
    "", "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
    "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre",
]


# ── Helpers ──────────────────────────────────────────────────────────────────

def _task_to_out(t: ActionTask) -> ActionTaskOut:
    return ActionTaskOut(
        id=str(t.id),
        plan_id=str(t.plan_id),
        title=t.title,
        description=t.description,
        source_agent=t.source_agent,
        status=t.status,
        priority=t.priority,
        owner=t.owner,
        due_date=t.due_date,
        tags=list(t.tags or []),
        order_index=t.order_index,
        created_at=t.created_at,
        updated_at=t.updated_at,
        explicacion=t.explicacion,
    )


def _plan_to_out(plan: ActionPlan, tasks: list[ActionTask]) -> ActionPlanOut:
    return ActionPlanOut(
        id=str(plan.id),
        board_session_id=str(plan.board_session_id),
        title=plan.title,
        created_at=plan.created_at,
        updated_at=plan.updated_at,
        tasks=[_task_to_out(t) for t in tasks],
    )


async def _get_board_session_or_404(
    bs_id: uuid.UUID, user_id: str, db: AsyncSession,
) -> BoardSession:
    result = await db.execute(
        select(BoardSession).where(
            BoardSession.id == bs_id, BoardSession.user_id == user_id,
        )
    )
    bs = result.scalar_one_or_none()
    if not bs:
        raise HTTPException(status_code=404, detail="Sesión no encontrada")
    return bs


async def _get_plan_with_tasks(
    bs_id: uuid.UUID, db: AsyncSession,
) -> tuple[ActionPlan | None, list[ActionTask]]:
    plan_result = await db.execute(
        select(ActionPlan).where(ActionPlan.board_session_id == bs_id)
    )
    plan = plan_result.scalar_one_or_none()
    if not plan:
        return None, []
    tasks_result = await db.execute(
        select(ActionTask)
        .where(ActionTask.plan_id == plan.id)
        .order_by(ActionTask.order_index, ActionTask.created_at)
    )
    return plan, list(tasks_result.scalars().all())


# ── POST /board-sessions/{id}/plan ───────────────────────────────────────────

@router.post("/board-sessions/{board_session_id}/plan", response_model=GeneratePlanResponse)
async def generate_or_replace_plan(
    board_session_id: uuid.UUID,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Genera el plan de acción a partir de los análisis. Si ya existe, lo regenera."""
    bs = await _get_board_session_or_404(board_session_id, user_id, db)

    if not bs.agent_analyses:
        raise HTTPException(
            status_code=400,
            detail="Primero ejecuta el análisis de los agentes antes de generar el plan.",
        )

    # Obtener memory_buffer para contexto de empresa
    onb_result = await db.execute(
        select(OnboardingSession).where(OnboardingSession.id == bs.onboarding_session_id)
    )
    onboarding = onb_result.scalar_one_or_none()
    memory_buffer = onboarding.memory_buffer if onboarding else {}

    period_label = f"{_MONTHS[bs.period_month]} {bs.period_year}"

    # 1. Reservar (o reutilizar) el plan ANTES del llamado lento al LLM,
    #    para que dos clicks consecutivos no generen un duplicate-key.
    plan_result = await db.execute(
        select(ActionPlan).where(ActionPlan.board_session_id == board_session_id)
    )
    plan = plan_result.scalar_one_or_none()

    if plan is None:
        plan = ActionPlan(
            board_session_id=board_session_id,
            user_id=user_id,
            title=f"Plan de acción — {period_label}",
        )
        db.add(plan)
        try:
            await db.flush()
        except IntegrityError:
            # Otra request creó el plan en paralelo — recuperar el existente
            await db.rollback()
            plan_result = await db.execute(
                select(ActionPlan).where(ActionPlan.board_session_id == board_session_id)
            )
            plan = plan_result.scalar_one()

    # 2. Generar tareas con el LLM (puede tardar 30s).
    new_tasks = generate_action_plan(bs.agent_analyses, memory_buffer, period_label)

    # 3. Reemplazar tareas existentes con las nuevas.
    await db.execute(delete(ActionTask).where(ActionTask.plan_id == plan.id))
    plan.updated_at = datetime.utcnow()

    task_objs = [
        ActionTask(
            plan_id=plan.id,
            title=t["title"],
            description=t.get("description"),
            source_agent=t.get("source_agent"),
            status="pendiente",
            priority=t.get("priority", "media"),
            owner=t.get("owner"),
            due_date=_parse_iso_date(t.get("due_date")),
            tags=t.get("tags", []),
            order_index=t.get("order_index", 0),
        )
        for t in new_tasks
    ]
    db.add_all(task_objs)
    await db.flush()
    await db.commit()
    await db.refresh(plan)

    return GeneratePlanResponse(
        plan_id=str(plan.id),
        task_count=len(task_objs),
        plan=_plan_to_out(plan, task_objs),
    )


# ── GET /board-sessions/{id}/plan ────────────────────────────────────────────

@router.get("/board-sessions/{board_session_id}/plan", response_model=ActionPlanOut)
async def get_plan(
    board_session_id: uuid.UUID,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Retorna el plan de acción con todas sus tareas."""
    await _get_board_session_or_404(board_session_id, user_id, db)
    plan, tasks = await _get_plan_with_tasks(board_session_id, db)
    if not plan:
        raise HTTPException(
            status_code=404,
            detail="Aún no se ha generado un plan de acción para esta sesión.",
        )
    return _plan_to_out(plan, tasks)


# ── POST /plans/{plan_id}/tasks ──────────────────────────────────────────────

@router.post("/plans/{plan_id}/tasks", response_model=ActionTaskOut)
async def create_task(
    plan_id: uuid.UUID,
    body: ActionTaskCreate,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Crea una tarea nueva en el plan (entrada manual)."""
    plan_result = await db.execute(
        select(ActionPlan).where(
            ActionPlan.id == plan_id, ActionPlan.user_id == user_id,
        )
    )
    plan = plan_result.scalar_one_or_none()
    if not plan:
        raise HTTPException(status_code=404, detail="Plan no encontrado")

    # Determinar order_index: máximo actual + 1
    max_idx_result = await db.execute(
        select(ActionTask.order_index)
        .where(ActionTask.plan_id == plan_id)
        .order_by(ActionTask.order_index.desc())
        .limit(1)
    )
    current_max = max_idx_result.scalar_one_or_none() or 0

    task = ActionTask(
        plan_id=plan_id,
        title=body.title,
        description=body.description,
        source_agent=body.source_agent,
        status=body.status,
        priority=body.priority,
        owner=body.owner,
        due_date=body.due_date,
        tags=body.tags,
        order_index=current_max + 1,
    )
    db.add(task)
    await db.flush()
    await db.commit()
    await db.refresh(task)
    return _task_to_out(task)


# ── PATCH /tasks/{task_id} ───────────────────────────────────────────────────

@router.patch("/tasks/{task_id}", response_model=ActionTaskOut)
async def update_task(
    task_id: uuid.UUID,
    body: ActionTaskUpdate,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Actualiza cualquier campo de una tarea (status, title, priority, etc.)."""
    task = await _get_user_task_or_404(task_id, user_id, db)

    payload = body.model_dump(exclude_unset=True)
    if payload.get("status") == "completada":
        count = await db.execute(
            select(func.count()).select_from(Evidence).where(Evidence.action_task_id == task.id)
        )
        if (count.scalar() or 0) == 0:
            raise HTTPException(
                status_code=409,
                detail="Se requiere al menos una evidencia para validar este acuerdo.",
            )

    for key, value in payload.items():
        setattr(task, key, value)
    task.updated_at = datetime.utcnow()

    await db.flush()
    await db.commit()
    await db.refresh(task)
    return _task_to_out(task)


# ── POST /tasks/{task_id}/explicacion ────────────────────────────────────────

async def _objetivo_empresa(task, user_id, db):
    objetivo = ""
    if task.objective_id is not None:
        obj = (await db.execute(select(Objective).where(Objective.id == task.objective_id))).scalar_one_or_none()
        objetivo = obj.title if obj else ""
    onb = (await db.execute(
        select(OnboardingSession).where(OnboardingSession.user_id == user_id)
        .order_by(OnboardingSession.created_at.desc())
    )).scalars().first()
    empresa = (((onb.memory_buffer if onb else {}) or {}).get("company") or {}).get("name") or ""
    return objetivo, empresa


@router.post("/tasks/{task_id}/explicacion")
async def explicar_tarea(
    task_id: uuid.UUID,
    user_id: str = Depends(get_current_user_id), db: AsyncSession = Depends(get_db),
):
    task = await _get_user_task_or_404(task_id, user_id, db)
    if task.explicacion:
        return task.explicacion
    objetivo, empresa = await _objetivo_empresa(task, user_id, db)
    data = await anyio.to_thread.run_sync(
        lambda: generate_explicacion(task.title, objetivo, empresa, task.kpi_ref))
    task.explicacion = data
    flag_modified(task, "explicacion")
    await db.commit()
    return data


# ── DELETE /tasks/{task_id} ──────────────────────────────────────────────────

@router.delete("/tasks/{task_id}")
async def delete_task(
    task_id: uuid.UUID,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Borra una tarea."""
    task = await _get_user_task_or_404(task_id, user_id, db)
    await db.delete(task)
    await db.commit()
    return {"deleted": True, "task_id": str(task_id)}


# ── Helpers ──────────────────────────────────────────────────────────────────

async def _get_user_task_or_404(
    task_id: uuid.UUID, user_id: str, db: AsyncSession,
) -> ActionTask:
    """
    Carga una tarea verificando propiedad por CUALQUIERA de los dos caminos:
    - legacy: plan_id → ActionPlan.user_id
    - plan anual: objective_id → MonthlyPlan → AnnualPlan.user_id
    """
    result = await db.execute(select(ActionTask).where(ActionTask.id == task_id))
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Tarea no encontrada")

    if task.plan_id is not None:
        owner = await db.execute(
            select(ActionPlan.id).where(
                ActionPlan.id == task.plan_id, ActionPlan.user_id == user_id,
            )
        )
        if owner.scalar_one_or_none() is not None:
            return task

    if task.objective_id is not None:
        owner = await db.execute(
            select(AnnualPlan.id)
            .select_from(Objective)
            .join(MonthlyPlan, Objective.monthly_plan_id == MonthlyPlan.id)
            .join(AnnualPlan, MonthlyPlan.annual_plan_id == AnnualPlan.id)
            .where(Objective.id == task.objective_id, AnnualPlan.user_id == user_id)
        )
        if owner.scalar_one_or_none() is not None:
            return task

    raise HTTPException(status_code=404, detail="Tarea no encontrada")


def _parse_iso_date(value):
    if not value:
        return None
    if isinstance(value, str):
        from datetime import date
        try:
            return date.fromisoformat(value)
        except (ValueError, TypeError):
            return None
    return value
