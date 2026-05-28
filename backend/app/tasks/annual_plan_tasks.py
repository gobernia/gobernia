"""
Tarea Celery: genera el plan estratégico de 12 meses tras cerrar el onboarding.
Corre en el worker (proceso síncrono) y envuelve la lógica async con asyncio.run,
igual que document_tasks. Crea su propia sesión de DB.
"""
import asyncio
import uuid

from app.tasks.worker import celery_app
from app.services.ai.annual_plan_generator import (
    generate_month_tasks, generate_skeleton, month_calendar,
    compute_active_month_index, synthesize_diagnostico,
)


def kpi_labels_from_buffer(memory_buffer: dict) -> list[str]:
    """Extrae los labels de todos los KPIs del onboarding (kpi_engine)."""
    labels: list[str] = []
    for kpis in (memory_buffer.get("kpis") or {}).values():
        for kpi in kpis or []:
            if isinstance(kpi, dict) and kpi.get("label"):
                labels.append(str(kpi["label"]))
    return labels


def run_diagnostico(memory_buffer: dict) -> tuple[dict, None]:
    """
    Paso 1: corre los 4 agentes sobre el memory_buffer del onboarding.
    Retorna (agent_analyses, None). Sin API key, cada agente devuelve su placeholder.
    """
    from app.services.ai.agents.base import run_agent_analysis
    from datetime import date

    today = date.today()
    analyses: dict[str, dict] = {}
    for agent in ("CFO", "CSO", "CRO", "Auditor"):
        analyses[agent] = run_agent_analysis(
            agent, memory_buffer, kpi_snapshot=memory_buffer.get("kpis"),
            period_year=today.year, period_month=today.month,
        )
    return analyses, None


@celery_app.task(name="generate_annual_plan", bind=True, max_retries=2)
def generate_annual_plan_task(self, annual_plan_id: str) -> dict:
    try:
        return asyncio.run(_entrypoint(annual_plan_id))
    except Exception as exc:
        raise self.retry(exc=exc, countdown=30)


async def _entrypoint(annual_plan_id: str) -> dict:
    from app.db.session import AsyncSessionLocal
    async with AsyncSessionLocal() as db:
        await _run_generation(annual_plan_id, db)
    return {"status": "active", "annual_plan_id": annual_plan_id}


async def _run_generation(annual_plan_id: str, db) -> None:
    """Llena un AnnualPlan en estado 'generating'. Marca 'failed' y re-lanza ante error."""
    from datetime import date
    from sqlalchemy import select
    from app.models.annual_plan import AnnualPlan, MonthlyPlan, Objective
    from app.models.action_plan import ActionTask
    from app.models.board_session import BoardSession
    from app.models.onboarding_session import OnboardingSession
    from app.api.v1.action_plans.router import _parse_iso_date

    plan = await db.get(AnnualPlan, uuid.UUID(annual_plan_id))
    if plan is None:
        return

    try:
        # Cargar el onboarding más reciente del usuario (memory_buffer).
        onb_res = await db.execute(
            select(OnboardingSession)
            .where(OnboardingSession.user_id == plan.user_id)
            .order_by(OnboardingSession.created_at.desc()).limit(1)
        )
        onboarding = onb_res.scalar_one_or_none()
        memory_buffer = (onboarding.memory_buffer if onboarding else {}) or {}

        # Paso 1: diagnóstico
        analyses, _ = run_diagnostico(memory_buffer)
        plan.diagnostico_summary = synthesize_diagnostico(analyses)

        # Sesión génesis que guarda los análisis (si hay onboarding)
        if onboarding is not None:
            genesis = BoardSession(
                onboarding_session_id=onboarding.id,
                user_id=plan.user_id,
                period_year=plan.start_date.year,
                period_month=plan.start_date.month,
                status="completed",
                agent_analyses=analyses,
            )
            db.add(genesis)
            await db.flush()
            plan.genesis_session_id = genesis.id

        # Paso 2: esqueleto
        skeleton = generate_skeleton(
            memory_buffer, plan.diagnostico_summary, kpi_labels_from_buffer(memory_buffer),
        )

        active_idx = compute_active_month_index(plan.start_date, date.today())

        # Paso 3: meses → objetivos → tareas
        for m in skeleton:
            year, month = month_calendar(plan.start_date.year, plan.start_date.month, m["month_index"])
            monthly = MonthlyPlan(
                annual_plan_id=plan.id,
                month_index=m["month_index"],
                period_year=year, period_month=month,
                focus=m.get("focus"),
                status="active" if m["month_index"] == active_idx else (
                    "done" if m["month_index"] < active_idx else "locked"),
            )
            db.add(monthly)
            await db.flush()

            objectives_models = []
            for oi, o in enumerate(m["objectives"]):
                obj = Objective(
                    monthly_plan_id=monthly.id,
                    title=o["title"], description=o.get("description"),
                    kpi_refs=o.get("kpi_refs", []), order_index=oi,
                )
                db.add(obj)
                objectives_models.append(obj)
            await db.flush()

            task_specs = generate_month_tasks(
                focus=m.get("focus"), objectives=m["objectives"],
                memory_buffer=memory_buffer, year=year, month=month,
            )
            for ts in task_specs:
                obj = objectives_models[ts["objective_index"]]
                db.add(ActionTask(
                    objective_id=obj.id,
                    title=ts["title"], description=ts.get("description"),
                    source_agent=None, status="pendiente",
                    priority=ts["priority"], owner=ts.get("owner"),
                    due_date=_parse_iso_date(ts.get("due_date")),
                    kpi_ref=ts.get("kpi_ref"),
                    tags=ts.get("tags", []), order_index=ts["order_index"],
                ))

        plan.status = "active"
        await db.commit()
    except Exception:
        plan.status = "failed"
        await db.commit()
        raise
