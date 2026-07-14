"""
Tarea Celery: genera el plan estratégico de N×12 meses tras cerrar el onboarding.
Orquestación trimestre-primero: hitos → quarters en paralelo → persistencia.
Corre en el worker (proceso síncrono) y envuelve la lógica async con asyncio.run,
igual que document_tasks. Crea su propia sesión de DB.
"""
import asyncio
import logging
import uuid

from app.tasks.worker import celery_app
from app.services.ai.agents.deliberacion import run_deliberacion_fundacional
from app.services.ai.annual_plan_generator import (
    generate_milestones, generate_quarter_plan, month_calendar,
    compute_active_month_index, due_date_within_month, synthesize_diagnostico,
)

_log = logging.getLogger(__name__)


def kpi_labels_from_buffer(memory_buffer: dict) -> list[str]:
    """Extrae los labels de todos los KPIs del onboarding (kpi_engine)."""
    labels: list[str] = []
    for kpis in (memory_buffer.get("kpis") or {}).values():
        for kpi in kpis or []:
            if isinstance(kpi, dict) and kpi.get("label"):
                labels.append(str(kpi["label"]))
    return labels


def run_diagnostico(memory_buffer: dict) -> tuple[dict, dict]:
    """
    Paso 1: corre los 4 agentes + Challenger (pre-mortem) + revisión sobre el
    memory_buffer del onboarding. Retorna (analyses_revisados, critiques).
    Sin API key, run_agent_analysis devuelve placeholder, el challenger devuelve {}
    y la revisión devuelve el análisis inicial — todo seguro.
    """
    from datetime import date
    from app.services.ai.agents.base import (
        run_agent_analysis, run_challenger_critique, run_agent_revision,
    )

    today = date.today()
    kpi_snapshot = memory_buffer.get("kpis")
    analyses: dict[str, dict] = {}
    critiques: dict[str, dict] = {}
    for agent in ("CFO", "CSO", "CRO", "Auditor"):
        initial = run_agent_analysis(
            agent, memory_buffer, kpi_snapshot=kpi_snapshot,
            period_year=today.year, period_month=today.month,
        )
        critique = run_challenger_critique(
            agent, initial, memory_buffer, kpi_snapshot, today.year, today.month,
        )
        revised = run_agent_revision(
            agent, initial, critique, memory_buffer, kpi_snapshot,
            today.year, today.month,
        )
        analyses[agent] = revised
        critiques[agent] = critique
    return analyses, critiques


@celery_app.task(name="generate_annual_plan", bind=True, max_retries=2)
def generate_annual_plan_task(self, annual_plan_id: str) -> dict:
    try:
        return asyncio.run(_entrypoint(annual_plan_id))
    except Exception as exc:
        raise self.retry(exc=exc, countdown=30)


async def _entrypoint(annual_plan_id: str) -> dict:
    from app.db.session import task_session
    async with task_session() as db:
        await _run_generation(annual_plan_id, db)
    return {"status": "active", "annual_plan_id": annual_plan_id}


# Cuántas llamadas de generación de tareas mensuales corren a la vez. Acota para no
# tronar los límites de rate de Anthropic; ajustable.
_MONTH_CONCURRENCY = 5


async def _generate_all_quarters(memory_buffer, kpi_labels, milestones, horizon):
    """Genera los quarters del horizonte EN PARALELO. Devuelve lista de quarter_results."""
    sem = asyncio.Semaphore(_MONTH_CONCURRENCY)
    quarters = [(y, q) for y in range(1, horizon + 1) for q in range(1, 5)]

    async def _one_quarter(y, q):
        async with sem:
            return await asyncio.to_thread(
                generate_quarter_plan, memory_buffer, kpi_labels, milestones, y, q)

    return await asyncio.gather(*[_one_quarter(y, q) for (y, q) in quarters])


async def _run_generation(annual_plan_id: str, db) -> None:
    """Llena un AnnualPlan en estado 'generating'. Marca 'failed' y re-lanza ante error."""
    from datetime import date
    from sqlalchemy import select, delete
    from app.models.annual_plan import AnnualPlan, MonthlyPlan, Objective
    from app.models.action_plan import ActionTask
    from app.models.board_session import BoardSession
    from app.models.onboarding_session import OnboardingSession

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

        # Inyectar FODA + metas priorizadas (del diagnóstico estratégico más reciente)
        # en el company_narrative para que el generador alinee el plan a lo prioritario.
        from app.models.diagnostico_estrategico import DiagnosticoEstrategico
        from app.services.ai.foda_into_plan import augment_buffer_with_foda
        diag = (await db.execute(
            select(DiagnosticoEstrategico).where(DiagnosticoEstrategico.user_id == plan.user_id)
            .order_by(DiagnosticoEstrategico.created_at.desc())
        )).scalars().first()
        dcont = (diag.content if diag else {}) or {}
        memory_buffer = augment_buffer_with_foda(
            memory_buffer, dcont.get("foda"), dcont.get("metas_orden") or [],
            perspectivas=dcont.get("perspectivas"))

        # Idempotencia (retry): borrar resultados de un intento previo.
        # El FK ondelete CASCADE en monthly_plans→objectives→action_tasks limpia en cascada.
        await db.execute(delete(MonthlyPlan).where(MonthlyPlan.annual_plan_id == plan.id))
        if plan.genesis_session_id is not None:
            await db.execute(delete(BoardSession).where(BoardSession.id == plan.genesis_session_id))
            plan.genesis_session_id = None

        # Paso 1: diagnóstico → el Consejo delibera → de su conclusión nace todo lo demás.
        analyses, critiques = run_diagnostico(memory_buffer)

        # La deliberación fundacional: cuatro análisis, UNA postura del órgano. Va aislada:
        # la generación del plan tarda minutos y cuesta dinero — no puede morir por esto.
        # Si falla, el diagnóstico cae a la concatenación de siempre y el plan se genera igual.
        deliberacion: dict | None = None
        try:
            deliberacion = await asyncio.to_thread(
                run_deliberacion_fundacional, analyses, critiques, memory_buffer, dcont)
        except Exception:
            _log.exception("la deliberación fundacional falló; el plan sigue sin ella")
            deliberacion = None

        conclusion_consejo = str((deliberacion or {}).get("conclusion") or "").strip()
        plan.diagnostico_summary = conclusion_consejo or synthesize_diagnostico(analyses)
        # Sin conclusión no hubo Consejo: el Roadmap no puede decir que nace de una postura vacía.
        postura_consejo = deliberacion if conclusion_consejo else None

        # Sesión génesis que guarda los análisis y la postura del Consejo (si hay onboarding)
        if onboarding is not None:
            genesis = BoardSession(
                onboarding_session_id=onboarding.id,
                user_id=plan.user_id,
                period_year=plan.start_date.year,
                period_month=plan.start_date.month,
                status="completed",
                agent_analyses=analyses,
                agent_critiques=critiques,
                conclusion=postura_consejo,
            )
            db.add(genesis)
            await db.flush()
            plan.genesis_session_id = genesis.id

        # Paso 2: hitos del horizonte
        horizon = plan.horizon_years or 3
        total_months = horizon * 12
        kpi_labels = kpi_labels_from_buffer(memory_buffer)

        milestones = await asyncio.to_thread(
            generate_milestones, memory_buffer, plan.diagnostico_summary, kpi_labels, horizon)
        plan.milestones = milestones

        active_idx = compute_active_month_index(plan.start_date, date.today(), total_months)

        # Paso 3: generar los N×4 quarters EN PARALELO
        quarter_results = await _generate_all_quarters(
            memory_buffer, kpi_labels, milestones, horizon)

        # Paso 4: persistir N×12 meses → objetivos → tareas (secuencial, rápido)
        for months in quarter_results:
            for mspec in months:
                mi = mspec["month_index"]
                year, month = month_calendar(
                    plan.start_date.year, plan.start_date.month, mi)
                status = ("active" if mi == active_idx
                          else ("done" if mi < active_idx else "locked"))
                monthly = MonthlyPlan(
                    annual_plan_id=plan.id,
                    month_index=mi,
                    period_year=year, period_month=month,
                    focus=mspec.get("focus"),
                    status=status,
                )
                db.add(monthly)
                await db.flush()

                for oi, ospec in enumerate(mspec.get("objectives") or []):
                    obj = Objective(
                        monthly_plan_id=monthly.id,
                        title=ospec["title"],
                        description=ospec.get("description"),
                        kpi_refs=ospec.get("kpi_refs") or [],
                        order_index=oi,
                    )
                    db.add(obj)
                    await db.flush()

                    for ti, tspec in enumerate(ospec.get("tasks") or []):
                        db.add(ActionTask(
                            objective_id=obj.id,
                            title=tspec["title"], description=tspec.get("description"),
                            owner=tspec.get("owner"), priority=tspec["priority"],
                            kpi_ref=tspec.get("kpi_ref"), required_doc=tspec.get("required_doc"),
                            tags=tspec.get("tags") or [],
                            due_date=due_date_within_month(
                                year, month, int(tspec.get("due_day", 28))),
                            order_index=ti, status="pendiente"))

        # Paso 5: el Roadmap NACE de la postura del Consejo (no bloquea el plan si falla).
        from app.services.ai.roadmap import generate_roadmap
        try:
            plan.roadmap = await asyncio.to_thread(
                generate_roadmap, memory_buffer, dcont, postura_consejo)
        except Exception:
            plan.roadmap = None

        plan.status = "active"
        await db.commit()
    except Exception:
        await db.rollback()
        plan = await db.get(AnnualPlan, uuid.UUID(annual_plan_id))
        if plan is not None:
            plan.status = "failed"
            await db.commit()
        raise
