"""
Plan estratégico de 12 meses — API REST.
- POST   /annual-plan/generate          → crea el plan (status generating) y encola la generación
- GET    /annual-plan/status            → estado + mes activo (para pantalla de carga)
- GET    /annual-plan                    → plan completo anidado (meses→objetivos→tareas)
- GET    /annual-plan/months/{idx}       → un mes
- POST   /annual-plan/objectives         → crear objetivo
- PATCH  /annual-plan/objectives/{id}    → editar objetivo
- DELETE /annual-plan/objectives/{id}    → borrar objetivo
- POST   /annual-plan/tasks              → crear tarea bajo un objetivo
(las tareas se editan/borran con los endpoints existentes PATCH/DELETE /tasks/{id})
"""
import uuid
from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.dependencies import get_current_user_id, get_db
from app.models.action_plan import ActionTask
from app.models.annual_plan import AnnualPlan, MonthlyPlan, Objective
from app.schemas.annual_plan import (
    AnnualPlanOut, AnnualPlanStatusOut, AnnualTaskCreate, MonthlyPlanOut,
    ObjectiveCreate, ObjectiveOut, ObjectiveUpdate,
)
from app.schemas.action_plan import ActionTaskOut
from app.services.ai.annual_plan_generator import compute_active_month_index

router = APIRouter()


# ── Serializers ───────────────────────────────────────────────────────────────

def _task_out(t: ActionTask) -> ActionTaskOut:
    return ActionTaskOut(
        id=str(t.id),
        plan_id=str(t.plan_id) if t.plan_id else None,
        objective_id=str(t.objective_id) if t.objective_id else None,
        kpi_ref=t.kpi_ref,
        title=t.title, description=t.description, source_agent=t.source_agent,
        status=t.status, priority=t.priority, owner=t.owner, due_date=t.due_date,
        tags=list(t.tags or []), order_index=t.order_index,
        created_at=t.created_at, updated_at=t.updated_at,
    )


def _objective_out(o: Objective, tasks: list[ActionTask]) -> ObjectiveOut:
    return ObjectiveOut(
        id=str(o.id), title=o.title, description=o.description,
        kpi_refs=list(o.kpi_refs or []), order_index=o.order_index,
        tasks=[_task_out(t) for t in tasks],
    )


# ── Helpers de carga ────────────────────────────────────────────────────────

async def _current_plan(user_id: str, db: AsyncSession) -> AnnualPlan | None:
    res = await db.execute(
        select(AnnualPlan)
        .where(AnnualPlan.user_id == user_id)
        .order_by(AnnualPlan.created_at.desc()).limit(1)
    )
    return res.scalar_one_or_none()


async def _tasks_by_objective(objective_ids: list[uuid.UUID], db: AsyncSession) -> dict:
    if not objective_ids:
        return {}
    res = await db.execute(
        select(ActionTask)
        .where(ActionTask.objective_id.in_(objective_ids))
        .order_by(ActionTask.order_index, ActionTask.created_at)
    )
    grouped: dict[uuid.UUID, list[ActionTask]] = {}
    for t in res.scalars().all():
        grouped.setdefault(t.objective_id, []).append(t)
    return grouped


# ── POST /annual-plan/generate ────────────────────────────────────────────────

@router.post("/annual-plan/generate", response_model=AnnualPlanStatusOut)
async def generate_plan(
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Crea el AnnualPlan en estado 'generating' y encola la generación en Celery.
    Si ya existe un plan que no falló, lo retorna sin duplicar."""
    existing = await _current_plan(user_id, db)
    if existing and existing.status != "failed":
        return AnnualPlanStatusOut(
            status=existing.status,
            active_month_index=compute_active_month_index(existing.start_date, date.today()),
        )

    plan = AnnualPlan(
        user_id=user_id, title="Plan estratégico de 12 meses",
        start_date=date.today(), status="generating",
    )
    db.add(plan)
    await db.flush()
    await db.commit()

    try:
        from app.tasks.annual_plan_tasks import generate_annual_plan_task
        generate_annual_plan_task.delay(str(plan.id))
    except Exception:
        # La cola (Redis/Celery) no está disponible: dejar el plan reintentable.
        plan.status = "failed"
        await db.commit()
        raise HTTPException(
            status_code=503,
            detail="No se pudo iniciar la generación del plan (cola no disponible). Intenta de nuevo más tarde.",
        )

    return AnnualPlanStatusOut(status="generating", active_month_index=1)


# ── GET /annual-plan/status ───────────────────────────────────────────────────

@router.get("/annual-plan/status", response_model=AnnualPlanStatusOut)
async def get_status(
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    plan = await _current_plan(user_id, db)
    if not plan:
        raise HTTPException(status_code=404, detail="No hay plan generado.")
    return AnnualPlanStatusOut(
        status=plan.status,
        active_month_index=compute_active_month_index(plan.start_date, date.today()),
    )


# ── GET /annual-plan ──────────────────────────────────────────────────────────

@router.get("/annual-plan", response_model=AnnualPlanOut)
async def get_plan(
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    res = await db.execute(
        select(AnnualPlan)
        .where(AnnualPlan.user_id == user_id)
        .order_by(AnnualPlan.created_at.desc()).limit(1)
        .options(selectinload(AnnualPlan.months).selectinload(MonthlyPlan.objectives))
    )
    plan = res.scalar_one_or_none()
    if not plan:
        raise HTTPException(status_code=404, detail="No hay plan generado.")

    all_obj_ids = [o.id for m in plan.months for o in m.objectives]
    grouped = await _tasks_by_objective(all_obj_ids, db)

    months_out = [
        MonthlyPlanOut(
            id=str(m.id), month_index=m.month_index,
            period_year=m.period_year, period_month=m.period_month,
            focus=m.focus, status=m.status, review=m.review,
            objectives=[_objective_out(o, grouped.get(o.id, [])) for o in m.objectives],
        )
        for m in plan.months
    ]
    return AnnualPlanOut(
        id=str(plan.id), title=plan.title, start_date=plan.start_date,
        status=plan.status, diagnostico_summary=plan.diagnostico_summary,
        genesis_session_id=str(plan.genesis_session_id) if plan.genesis_session_id else None,
        months=months_out,
    )


# ── GET /annual-plan/months/{idx} ─────────────────────────────────────────────

@router.get("/annual-plan/months/{month_index}", response_model=MonthlyPlanOut)
async def get_month(
    month_index: int,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    plan = await _current_plan(user_id, db)
    if not plan:
        raise HTTPException(status_code=404, detail="No hay plan generado.")
    res = await db.execute(
        select(MonthlyPlan)
        .where(MonthlyPlan.annual_plan_id == plan.id, MonthlyPlan.month_index == month_index)
        .options(selectinload(MonthlyPlan.objectives))
    )
    month = res.scalar_one_or_none()
    if not month:
        raise HTTPException(status_code=404, detail="Mes no encontrado.")
    grouped = await _tasks_by_objective([o.id for o in month.objectives], db)
    return MonthlyPlanOut(
        id=str(month.id), month_index=month.month_index,
        period_year=month.period_year, period_month=month.period_month,
        focus=month.focus, status=month.status, review=month.review,
        objectives=[_objective_out(o, grouped.get(o.id, [])) for o in month.objectives],
    )


# ── CRUD de objetivos ─────────────────────────────────────────────────────────

async def _owned_objective(obj_id: uuid.UUID, user_id: str, db: AsyncSession) -> Objective:
    res = await db.execute(
        select(Objective)
        .join(MonthlyPlan, Objective.monthly_plan_id == MonthlyPlan.id)
        .join(AnnualPlan, MonthlyPlan.annual_plan_id == AnnualPlan.id)
        .where(Objective.id == obj_id, AnnualPlan.user_id == user_id)
    )
    obj = res.scalar_one_or_none()
    if not obj:
        raise HTTPException(status_code=404, detail="Objetivo no encontrado.")
    return obj


@router.post("/annual-plan/objectives", response_model=ObjectiveOut)
async def create_objective(
    body: ObjectiveCreate,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    res = await db.execute(
        select(MonthlyPlan)
        .join(AnnualPlan, MonthlyPlan.annual_plan_id == AnnualPlan.id)
        .where(MonthlyPlan.id == uuid.UUID(body.monthly_plan_id), AnnualPlan.user_id == user_id)
    )
    if not res.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Mes no encontrado.")
    obj = Objective(
        monthly_plan_id=uuid.UUID(body.monthly_plan_id),
        title=body.title, description=body.description, kpi_refs=body.kpi_refs,
    )
    db.add(obj)
    await db.flush()
    await db.commit()
    await db.refresh(obj)
    return _objective_out(obj, [])


@router.patch("/annual-plan/objectives/{objective_id}", response_model=ObjectiveOut)
async def update_objective(
    objective_id: uuid.UUID,
    body: ObjectiveUpdate,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    obj = await _owned_objective(objective_id, user_id, db)
    for key, value in body.model_dump(exclude_unset=True).items():
        setattr(obj, key, value)
    obj.updated_at = datetime.utcnow()
    await db.flush()
    await db.commit()
    await db.refresh(obj)
    grouped = await _tasks_by_objective([obj.id], db)
    return _objective_out(obj, grouped.get(obj.id, []))


@router.delete("/annual-plan/objectives/{objective_id}")
async def delete_objective(
    objective_id: uuid.UUID,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    obj = await _owned_objective(objective_id, user_id, db)
    await db.delete(obj)
    await db.commit()
    return {"deleted": True, "objective_id": str(objective_id)}


# ── POST /annual-plan/tasks ───────────────────────────────────────────────────

@router.post("/annual-plan/tasks", response_model=ActionTaskOut)
async def create_task(
    body: AnnualTaskCreate,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    obj = await _owned_objective(uuid.UUID(body.objective_id), user_id, db)
    max_idx = await db.execute(
        select(ActionTask.order_index)
        .where(ActionTask.objective_id == obj.id)
        .order_by(ActionTask.order_index.desc()).limit(1)
    )
    current_max = max_idx.scalar_one_or_none() or 0
    task = ActionTask(
        objective_id=obj.id, title=body.title, description=body.description,
        status=body.status, priority=body.priority, owner=body.owner,
        due_date=body.due_date, kpi_ref=body.kpi_ref, tags=body.tags,
        order_index=current_max + 1,
    )
    db.add(task)
    await db.flush()
    await db.commit()
    await db.refresh(task)
    return _task_out(task)
