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

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user_id, get_db
from app.models.action_plan import ActionPlan, ActionTask
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
    new_tasks = generate_action_plan(bs.agent_analyses, memory_buffer, period_label)

    # Si ya existe plan, borrar tareas y reusar plan_id (mantiene historial)
    plan_result = await db.execute(
        select(ActionPlan).where(ActionPlan.board_session_id == board_session_id)
    )
    plan = plan_result.scalar_one_or_none()

    if plan:
        # Borrar tareas existentes para regenerar
        from sqlalchemy import delete
        await db.execute(delete(ActionTask).where(ActionTask.plan_id == plan.id))
        plan.updated_at = datetime.utcnow()
    else:
        plan = ActionPlan(
            board_session_id=board_session_id,
            user_id=user_id,
            title=f"Plan de acción — {period_label}",
        )
        db.add(plan)
        await db.flush()

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
    for key, value in payload.items():
        setattr(task, key, value)
    task.updated_at = datetime.utcnow()

    await db.flush()
    await db.commit()
    await db.refresh(task)
    return _task_to_out(task)


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
    """Carga una tarea verificando que el plan pertenezca al user_id."""
    result = await db.execute(
        select(ActionTask, ActionPlan)
        .join(ActionPlan, ActionTask.plan_id == ActionPlan.id)
        .where(ActionTask.id == task_id, ActionPlan.user_id == user_id)
    )
    row = result.first()
    if not row:
        raise HTTPException(status_code=404, detail="Tarea no encontrada")
    return row[0]


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
