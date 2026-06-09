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

import anyio
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.dependencies import get_current_user_id, get_db
from app.models.action_plan import ActionTask
from app.models.annual_plan import AnnualPlan, MonthlyPlan, Objective
from app.models.evidence import Evidence
from app.schemas.annual_plan import (
    AnnualPlanOut, AnnualPlanStatusOut, AnnualTaskCreate, MonthlyPlanOut,
    ObjectiveCreate, ObjectiveOut, ObjectiveUpdate,
    CloseMonthRequest, ApplyProposalRequest,
)
from app.schemas.action_plan import ActionTaskOut
from app.models.board_theme import BoardTheme
from app.schemas.board_theme import BoardThemeOut, BoardThemeCreate, BoardThemeUpdate
from app.services.ai.annual_plan_generator import compute_active_month_index
from app.services.ai.month_review import compute_signals, run_month_review
from app.services.ai.agents.base import _MONTH_NAMES
from app.services.governance.theme_seeder import seed_default_themes
from app.schemas.orden_del_dia import OrdenDelDiaOut, ThemeRef
from app.services.governance.coverage_calendar import scheduled_for_session
from app.schemas.coverage import CoverageRow, CoverageMarkIn
from app.services.governance.coverage_board import coverage_rows
from sqlalchemy.orm.attributes import flag_modified as _flag_modified

router = APIRouter()


# ── Serializers ───────────────────────────────────────────────────────────────

def _task_out(t: ActionTask, evidence_count: int = 0) -> ActionTaskOut:
    return ActionTaskOut(
        id=str(t.id),
        plan_id=str(t.plan_id) if t.plan_id else None,
        objective_id=str(t.objective_id) if t.objective_id else None,
        kpi_ref=t.kpi_ref,
        title=t.title, description=t.description, source_agent=t.source_agent,
        status=t.status, priority=t.priority, owner=t.owner, due_date=t.due_date,
        tags=list(t.tags or []), order_index=t.order_index,
        created_at=t.created_at, updated_at=t.updated_at,
        evidence_count=evidence_count,
    )


def _objective_out(o: Objective, tasks: list[ActionTask], evidence_counts: dict | None = None) -> ObjectiveOut:
    counts = evidence_counts or {}
    return ObjectiveOut(
        id=str(o.id), title=o.title, description=o.description,
        kpi_refs=list(o.kpi_refs or []), order_index=o.order_index,
        tasks=[_task_out(t, counts.get(t.id, 0)) for t in tasks],
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
    await seed_default_themes(db, plan.id)
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

    task_ids = [t.id for tasks in grouped.values() for t in tasks]
    evidence_counts: dict = {}
    if task_ids:
        cres = await db.execute(
            select(Evidence.action_task_id, func.count())
            .where(Evidence.action_task_id.in_(task_ids))
            .group_by(Evidence.action_task_id)
        )
        evidence_counts = {tid: cnt for tid, cnt in cres.all()}

    months_out = [
        MonthlyPlanOut(
            id=str(m.id), month_index=m.month_index,
            period_year=m.period_year, period_month=m.period_month,
            focus=m.focus, status=m.status, review=m.review,
            objectives=[_objective_out(o, grouped.get(o.id, []), evidence_counts) for o in m.objectives],
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


# ── Cierre de mes / revisión ──────────────────────────────────────────────────

async def _load_owned_month(month_index: int, user_id: str, db: AsyncSession) -> MonthlyPlan | None:
    plan = await _current_plan(user_id, db)
    if not plan:
        return None
    res = await db.execute(
        select(MonthlyPlan)
        .where(MonthlyPlan.annual_plan_id == plan.id, MonthlyPlan.month_index == month_index)
        .options(selectinload(MonthlyPlan.objectives))
    )
    return res.scalar_one_or_none()


async def _get_or_create_carryover_objective(monthly_plan_id: uuid.UUID, db: AsyncSession) -> Objective:
    res = await db.execute(
        select(Objective).where(
            Objective.monthly_plan_id == monthly_plan_id,
            Objective.title == "Tareas arrastradas",
        )
    )
    obj = res.scalar_one_or_none()
    if obj is None:
        obj = Objective(monthly_plan_id=monthly_plan_id, title="Tareas arrastradas",
                        kpi_refs=[], order_index=99)
        db.add(obj)
        await db.flush()
    return obj


async def _run_close(month: MonthlyPlan, kpis: dict, user_id: str) -> dict:
    """
    Corre la revisión y persiste en sesiones nuevas (patrón /analyse: los agentes
    corren fuera de la conexión de la request). Devuelve {month_index, active_month_index, grade}.
    """
    from app.db.session import AsyncSessionLocal
    from sqlalchemy.orm.attributes import flag_modified
    from app.models.onboarding_session import OnboardingSession

    today = date.today()
    obj_ids = [o.id for o in month.objectives]
    month_id = month.id
    month_index = month.month_index
    annual_plan_id = month.annual_plan_id
    focus = month.focus
    period_label = f"{_MONTH_NAMES[month.period_month]} {month.period_year}"
    objectives = [{"title": o.title} for o in month.objectives]

    async with AsyncSessionLocal() as db:
        tasks = []
        if obj_ids:
            res = await db.execute(select(ActionTask).where(ActionTask.objective_id.in_(obj_ids)))
            tasks = list(res.scalars().all())
        onb = await db.execute(
            select(OnboardingSession).where(OnboardingSession.user_id == user_id)
            .order_by(OnboardingSession.created_at.desc()).limit(1)
        )
        onboarding = onb.scalar_one_or_none()
        memory_buffer = (onboarding.memory_buffer if onboarding else {}) or {}
        incomplete_ids = [str(t.id) for t in tasks if t.status != "completada"]
        signals = compute_signals(tasks, kpis, memory_buffer, today)

    review = await anyio.to_thread.run_sync(
        lambda: run_month_review(
            signals=signals, month_focus=focus, objectives=objectives,
            memory_buffer=memory_buffer, period_label=period_label,
            incomplete_task_ids=incomplete_ids,
        )
    )
    review["closed_at"] = today.isoformat()
    review["signals"] = signals
    for p in review["proposals"]:
        p["id"] = str(uuid.uuid4())
        p["applied"] = False

    async with AsyncSessionLocal() as db:
        m = await db.get(MonthlyPlan, month_id)
        m.review = review
        m.status = "done"
        flag_modified(m, "review")
        nxt = await db.execute(
            select(MonthlyPlan).where(
                MonthlyPlan.annual_plan_id == annual_plan_id,
                MonthlyPlan.month_index == month_index + 1,
            )
        )
        nxt_m = nxt.scalar_one_or_none()
        if nxt_m is not None and nxt_m.status == "locked":
            nxt_m.status = "active"
        await db.commit()

    active_idx = month_index + 1 if month_index < 12 else month_index
    return {"month_index": month_index, "active_month_index": active_idx, "grade": review["grade"]}


@router.post("/annual-plan/months/{month_index}/close")
async def close_month(
    month_index: int,
    body: CloseMonthRequest,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    month = await _load_owned_month(month_index, user_id, db)
    if month is None:
        raise HTTPException(status_code=404, detail="Mes no encontrado.")
    if month.status != "active":
        raise HTTPException(status_code=409, detail="Solo puedes cerrar el mes activo.")
    return await _run_close(month, body.kpis, user_id)


@router.post("/annual-plan/months/{month_index}/apply-proposal")
async def apply_proposal(
    month_index: int,
    body: ApplyProposalRequest,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    from sqlalchemy.orm.attributes import flag_modified
    month = await _load_owned_month(month_index, user_id, db)
    if month is None or not month.review:
        raise HTTPException(status_code=404, detail="Mes o revisión no encontrada.")

    review = dict(month.review)
    proposals = review.get("proposals", [])
    prop = next((p for p in proposals if p.get("id") == body.proposal_id), None)
    if prop is None:
        raise HTTPException(status_code=404, detail="Propuesta no encontrada.")
    if prop.get("applied"):
        return review

    nxt_res = await db.execute(
        select(MonthlyPlan).where(
            MonthlyPlan.annual_plan_id == month.annual_plan_id,
            MonthlyPlan.month_index == month.month_index + 1,
        )
    )
    nxt = nxt_res.scalar_one_or_none()
    if nxt is None:
        raise HTTPException(status_code=409, detail="No hay mes siguiente para aplicar la propuesta.")

    t = prop["type"]
    if t == "carry_over_task":
        carry = await _get_or_create_carryover_objective(nxt.id, db)
        task = (await db.execute(
            select(ActionTask).where(ActionTask.id == uuid.UUID(prop["task_id"]))
        )).scalar_one_or_none()
        if task is not None:
            task.objective_id = carry.id
    elif t == "new_objective":
        db.add(Objective(monthly_plan_id=nxt.id, title=prop["title"],
                         description=prop.get("description"), kpi_refs=prop.get("kpi_refs", [])))
    elif t == "new_task":
        # El objetivo destino debe existir y pertenecer al mes siguiente (evita FK 500
        # si se aplica la tarea antes que su objetivo, o con un id inventado por el LLM).
        target_obj = (await db.execute(
            select(Objective).where(
                Objective.id == uuid.UUID(prop["objective_id"]),
                Objective.monthly_plan_id == nxt.id,
            )
        )).scalar_one_or_none()
        if target_obj is None:
            raise HTTPException(
                status_code=409,
                detail="El objetivo destino no existe en el mes siguiente. Aplica primero el objetivo propuesto.",
            )
        db.add(ActionTask(objective_id=target_obj.id, title=prop["title"],
                          status="pendiente", priority=prop.get("priority", "media"),
                          owner=prop.get("owner"), kpi_ref=prop.get("kpi_ref"),
                          tags=[], order_index=0))

    prop["applied"] = True
    month.review = review
    flag_modified(month, "review")
    await db.flush()
    await db.commit()
    return review


# ── Temas del Consejo (B1) ────────────────────────────────────────────────────

def _theme_out(t: BoardTheme) -> BoardThemeOut:
    return BoardThemeOut(
        id=str(t.id), key=t.key, label=t.label, type=t.type,
        every_n_sessions=t.every_n_sessions, active=t.active,
        is_default=t.is_default, order_index=t.order_index,
    )


def _slugify(label: str) -> str:
    base = "".join(c if c.isalnum() else "_" for c in label.lower()).strip("_")
    return (base or "tema")[:50] + "_" + uuid.uuid4().hex[:6]


async def _load_owned_theme(theme_id: uuid.UUID, user_id: str, db: AsyncSession) -> BoardTheme:
    res = await db.execute(
        select(BoardTheme)
        .join(AnnualPlan, BoardTheme.annual_plan_id == AnnualPlan.id)
        .where(BoardTheme.id == theme_id, AnnualPlan.user_id == user_id)
    )
    theme = res.scalar_one_or_none()
    if not theme:
        raise HTTPException(status_code=404, detail="Tema no encontrado")
    return theme


@router.get("/annual-plan/themes", response_model=list[BoardThemeOut])
async def list_themes(
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    plan = await _current_plan(user_id, db)
    if not plan:
        raise HTTPException(status_code=404, detail="No tienes un plan anual")
    res = await db.execute(
        select(BoardTheme)
        .where(BoardTheme.annual_plan_id == plan.id)
        .order_by(BoardTheme.type, BoardTheme.order_index)
    )
    return [_theme_out(t) for t in res.scalars().all()]


@router.post("/annual-plan/themes", response_model=BoardThemeOut)
async def create_theme(
    body: BoardThemeCreate,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    plan = await _current_plan(user_id, db)
    if not plan:
        raise HTTPException(status_code=404, detail="No tienes un plan anual")
    theme = BoardTheme(
        annual_plan_id=plan.id, key=_slugify(body.label), label=body.label,
        type=body.type, every_n_sessions=body.every_n_sessions,
        is_default=False, active=True, order_index=999,
    )
    db.add(theme)
    await db.flush()
    return _theme_out(theme)


@router.patch("/annual-plan/themes/{theme_id}", response_model=BoardThemeOut)
async def update_theme(
    theme_id: uuid.UUID,
    body: BoardThemeUpdate,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    theme = await _load_owned_theme(theme_id, user_id, db)
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(theme, field, value)
    await db.flush()
    return _theme_out(theme)


@router.delete("/annual-plan/themes/{theme_id}", status_code=204)
async def delete_theme(
    theme_id: uuid.UUID,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    theme = await _load_owned_theme(theme_id, user_id, db)
    await db.delete(theme)
    await db.flush()


# ── Orden del día (B2) ────────────────────────────────────────────────────────

def _theme_ref(t: BoardTheme) -> ThemeRef:
    return ThemeRef(key=t.key, label=t.label, every_n_sessions=t.every_n_sessions)


@router.get("/annual-plan/months/{month_index}/orden-del-dia", response_model=OrdenDelDiaOut)
async def get_orden_del_dia(
    month_index: int,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    plan = await _current_plan(user_id, db)
    if not plan:
        raise HTTPException(status_code=404, detail="No hay plan generado.")

    res = await db.execute(
        select(BoardTheme).where(BoardTheme.annual_plan_id == plan.id)
    )
    themes = list(res.scalars().all())

    mres = await db.execute(
        select(MonthlyPlan)
        .where(MonthlyPlan.annual_plan_id == plan.id, MonthlyPlan.month_index == month_index)
        .options(selectinload(MonthlyPlan.objectives))
    )
    month = mres.scalar_one_or_none()
    if not month:
        raise HTTPException(status_code=404, detail="Mes no encontrado.")

    sched = scheduled_for_session(themes, month_index)
    grouped = await _tasks_by_objective([o.id for o in month.objectives], db)
    return OrdenDelDiaOut(
        month_index=month.month_index,
        period_year=month.period_year,
        period_month=month.period_month,
        permanent_themes=[_theme_ref(t) for t in sched["permanente"]],
        coverage_themes=[_theme_ref(t) for t in sched["cobertura"]],
        covered_keys=list(month.covered_themes or []),
        objectives=[_objective_out(o, grouped.get(o.id, [])) for o in month.objectives],
    )


# ── Cobertura (B4) ────────────────────────────────────────────────────────────

@router.get("/annual-plan/cobertura", response_model=list[CoverageRow])
async def get_cobertura(
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    plan = await _current_plan(user_id, db)
    if not plan:
        raise HTTPException(status_code=404, detail="No hay plan generado.")
    tres = await db.execute(select(BoardTheme).where(BoardTheme.annual_plan_id == plan.id))
    themes = list(tres.scalars().all())
    mres = await db.execute(select(MonthlyPlan).where(MonthlyPlan.annual_plan_id == plan.id))
    months = list(mres.scalars().all())
    active = compute_active_month_index(plan.start_date, date.today())
    return [CoverageRow(**row) for row in coverage_rows(themes, months, active)]


@router.post("/annual-plan/months/{month_index}/coverage")
async def mark_coverage(
    month_index: int,
    body: CoverageMarkIn,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    plan = await _current_plan(user_id, db)
    if not plan:
        raise HTTPException(status_code=404, detail="No hay plan generado.")
    active = compute_active_month_index(plan.start_date, date.today())
    if month_index > active:
        raise HTTPException(status_code=400, detail="No puedes marcar cobertura de una sesión futura.")
    mres = await db.execute(
        select(MonthlyPlan).where(
            MonthlyPlan.annual_plan_id == plan.id, MonthlyPlan.month_index == month_index
        )
    )
    month = mres.scalar_one_or_none()
    if not month:
        raise HTTPException(status_code=404, detail="Mes no encontrado.")
    keys = list(month.covered_themes or [])
    if body.covered and body.theme_key not in keys:
        keys.append(body.theme_key)
    elif not body.covered and body.theme_key in keys:
        keys.remove(body.theme_key)
    month.covered_themes = keys
    _flag_modified(month, "covered_themes")
    await db.flush()
    return {"month_index": month_index, "covered_themes": keys}
