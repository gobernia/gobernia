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
import base64
import copy
import secrets
import uuid
from datetime import date, datetime, timedelta, timezone

import anyio
from fastapi import APIRouter, Body, Depends, HTTPException, Response
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.v1.company.service import get_logo_bytes
from app.core.dependencies import get_current_user_id, get_db
from app.models.action_plan import ActionTask
from app.models.annual_plan import AnnualPlan, MonthlyPlan, Objective
from app.models.evidence import Evidence
from app.models.roadmap_version import RoadmapVersion
from app.schemas.annual_plan import (
    AnnualPlanOut, AnnualPlanStatusOut, AnnualTaskCreate, MonthlyPlanOut,
    ObjectiveCreate, ObjectiveOut, ObjectiveUpdate,
    CloseMonthRequest, ApplyProposalRequest, GeneratePlanRequest,
)
from app.schemas.action_plan import ActionTaskOut
from app.schemas.board import BoardOut, BoardMonthOut, BoardTaskOut
from app.models.board_theme import BoardTheme
from app.schemas.board_theme import BoardThemeOut, BoardThemeCreate, BoardThemeUpdate
from app.services.ai.annual_plan_generator import compute_active_month_index
from app.services.ai.month_review import compute_signals, run_month_review, select_review_documents
from app.services.documents.storage import download_from_storage
from app.services.ai.agents.base import _MONTH_NAMES
from app.services.governance.theme_seeder import seed_default_themes
from app.schemas.orden_del_dia import OrdenDelDiaOut, ThemeRef
from app.services.governance.coverage_calendar import scheduled_for_session
from app.schemas.coverage import CoverageRow, CoverageMarkIn
from app.services.governance.coverage_board import coverage_rows
from sqlalchemy.orm.attributes import flag_modified as _flag_modified
from app.models.onboarding_session import OnboardingSession
from app.services.pdf.orden_del_dia_pdf import build_orden_pdf
from app.schemas.alerts import AlertItem
from app.services.governance.alerts import compute_alerts, review_alert
from app.schemas.agenda import AgendaItem, AgendaOut
from app.services.governance.agenda_engine import build_agenda
from app.services.ai.agenda_chair import chair_curate_agenda
from app.schemas.minuta import MinutaOut, DecisionIn
from app.services.ai.minuta import generate_minuta
from app.models.compromiso import Compromiso

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
        required_doc=t.required_doc,
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


# Si la generación tarda más que esto, asumimos que el worker murió/falló sin marcarlo.
_GENERATING_TIMEOUT = timedelta(minutes=30)


async def _expire_if_stale(plan: AnnualPlan | None, db: AsyncSession) -> AnnualPlan | None:
    """Blindaje: un plan colgado en 'generating' (worker caído o error que rompió la
    conexión antes de marcar 'failed') se pasa a 'failed' para que sea reintentable en vez
    de quedarse pensando para siempre."""
    if (plan is not None and plan.status == "generating"
            and plan.created_at is not None
            and datetime.now(timezone.utc) - plan.created_at > _GENERATING_TIMEOUT):
        plan.status = "failed"
        await db.commit()
    return plan


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
    body: GeneratePlanRequest = GeneratePlanRequest(),
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Crea el AnnualPlan en estado 'generating' y encola la generación en Celery.
    Si ya existe un plan que no falló, lo retorna sin duplicar."""
    onb = await db.execute(
        select(OnboardingSession).where(OnboardingSession.user_id == user_id)
        .order_by(OnboardingSession.created_at.desc()).limit(1)
    )
    onboarding = onb.scalar_one_or_none()
    if not onboarding or 8 not in (onboarding.completed_stages or []):
        raise HTTPException(
            status_code=400,
            detail="Debes completar el onboarding antes de generar tu plan.",
        )
    # El plan se construye del diagnóstico + FODA, así que basta el perfil de empresa.
    # No exigimos KPIs numéricos (el onboarding de Todd no los fuerza).
    if not ((onboarding.memory_buffer or {}).get("company") or {}).get("name"):
        raise HTTPException(
            status_code=400,
            detail="Completa el perfil de tu empresa con Todd antes de generar tu plan.",
        )

    existing = await _expire_if_stale(await _current_plan(user_id, db), db)
    if existing and existing.status != "failed":
        return AnnualPlanStatusOut(
            status=existing.status,
            active_month_index=compute_active_month_index(existing.start_date, date.today(), total_months=(existing.horizon_years or 1) * 12),
        )

    plan = AnnualPlan(
        user_id=user_id, title=f"Plan estratégico de {body.horizon_years} año(s)",
        start_date=date.today(), status="generating",
        horizon_years=body.horizon_years,
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
    plan = await _expire_if_stale(await _current_plan(user_id, db), db)
    if not plan:
        raise HTTPException(status_code=404, detail="No hay plan generado.")
    return AnnualPlanStatusOut(
        status=plan.status,
        active_month_index=compute_active_month_index(plan.start_date, date.today(), total_months=(plan.horizon_years or 1) * 12),
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
        horizon_years=plan.horizon_years,
        milestones=plan.milestones,
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


# ── GET /annual-plan/board ────────────────────────────────────────────────────
# Tablero operativo (tipo Monday): TODAS las tareas del plan activo, agrupadas por
# mes en orden cronológico. Sin candado de evidencia — es el rastreador operativo.

@router.get("/annual-plan/board", response_model=BoardOut)
async def get_board(
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    plan = await _current_plan(user_id, db)
    if not plan:
        return BoardOut(meses=[])

    mres = await db.execute(
        select(MonthlyPlan)
        .where(MonthlyPlan.annual_plan_id == plan.id)
        .order_by(MonthlyPlan.month_index)
        .options(selectinload(MonthlyPlan.objectives))
    )
    months = list(mres.scalars().all())

    obj_ids = [o.id for m in months for o in m.objectives]
    grouped = await _tasks_by_objective(obj_ids, db)
    obj_title = {o.id: o.title for m in months for o in m.objectives}

    # Conteo de evidencias por tarea en UNA sola query (sin N+1).
    task_ids = [t.id for tasks in grouped.values() for t in tasks]
    evidence_counts: dict = {}
    if task_ids:
        cres = await db.execute(
            select(Evidence.action_task_id, func.count())
            .where(Evidence.action_task_id.in_(task_ids))
            .group_by(Evidence.action_task_id)
        )
        evidence_counts = {tid: cnt for tid, cnt in cres.all()}

    active = compute_active_month_index(
        plan.start_date, date.today(), total_months=(plan.horizon_years or 1) * 12
    )

    def _validacion_out(v: dict | None) -> dict | None:
        # Al frontend solo le importa el veredicto, no el rastro interno (validated_at, sesión).
        if not v:
            return None
        return {"estado": v.get("estado"), "motivo": v.get("motivo")}

    def _board_task(t: ActionTask, viene_de: str | None = None) -> BoardTaskOut:
        return BoardTaskOut(
            id=str(t.id), title=t.title, owner=t.owner,
            status=t.status, priority=t.priority, due_date=t.due_date,
            objetivo=obj_title.get(t.objective_id),
            viene_de=viene_de,
            evidencias=evidence_counts.get(t.id, 0),
            validacion=_validacion_out(t.validacion),
        )

    def _month_tareas(m: MonthlyPlan) -> list[ActionTask]:
        ts = [t for o in m.objectives for t in grouped.get(o.id, [])]
        ts.sort(key=lambda t: t.order_index)
        return ts

    meses_out = []
    for m in months:
        # Las tareas PROPIAS del mes (con su status real). Los meses pasados NO se mutan.
        tareas = [_board_task(t) for t in _month_tareas(m)]

        # El arrastre es a nivel de VISTA: solo el mes actual reúne, en una lista aparte,
        # las tareas incompletas cuyos meses ya pasaron (marcadas con su mes de origen).
        arrastradas: list[BoardTaskOut] = []
        if m.month_index == active:
            for prev in months:
                if prev.month_index >= active:
                    continue
                prev_label = f"{_MONTH_NAMES[prev.period_month]} {prev.period_year}"
                for t in _month_tareas(prev):
                    if t.status != "completada":
                        arrastradas.append(_board_task(t, viene_de=prev_label))

        meses_out.append(BoardMonthOut(
            month_index=m.month_index,
            period_year=m.period_year,
            period_month=m.period_month,
            label=f"{_MONTH_NAMES[m.period_month]} {m.period_year}",
            es_mes_actual=(m.month_index == active),
            tareas=tareas,
            arrastradas=arrastradas,
        ))
    return BoardOut(meses=meses_out)


# ── Roadmap estratégico ───────────────────────────────────────────────────────

@router.get("/annual-plan/roadmap")
async def get_roadmap(
    user_id: str = Depends(get_current_user_id), db: AsyncSession = Depends(get_db),
):
    plan = await _current_plan(user_id, db)
    if plan is None:
        raise HTTPException(status_code=404, detail="No hay plan generado.")
    return plan.roadmap or {}


@router.patch("/annual-plan/roadmap")
async def patch_roadmap(
    body: dict = Body(...),
    user_id: str = Depends(get_current_user_id), db: AsyncSession = Depends(get_db),
):
    plan = await _current_plan(user_id, db)
    if plan is None:
        raise HTTPException(status_code=404, detail="No hay plan generado.")
    if plan.roadmap_status == "validado":
        raise HTTPException(
            status_code=409,
            detail="El roadmap está validado y es solo lectura. Reábrelo para editarlo.",
        )
    plan.roadmap = body
    _flag_modified(plan, "roadmap")
    await db.commit()
    return plan.roadmap


# ── Ciclo de validación del roadmap ──────────────────────────────────────────
# borrador (editable) → validado (solo lectura, queda registrado para el consejo).

_ROADMAP_THEME_KEY = "roadmap_validado"
_ROADMAP_THEME_LABEL = "Revisión del Roadmap estratégico"


def _estado_out(plan: AnnualPlan, version_actual: int = 0) -> dict:
    return {
        "status": plan.roadmap_status or "borrador",
        "validated_at": plan.roadmap_validated_at,
        # Cuántas versiones validadas se han archivado (0 = nunca se validó).
        "version_actual": version_actual,
    }


async def _count_versions(plan: AnnualPlan, db: AsyncSession) -> int:
    n = (await db.execute(
        select(func.max(RoadmapVersion.version)).where(RoadmapVersion.plan_id == plan.id)
    )).scalar()
    return n or 0


@router.get("/annual-plan/roadmap/estado")
async def get_roadmap_estado(
    user_id: str = Depends(get_current_user_id), db: AsyncSession = Depends(get_db),
):
    plan = await _current_plan(user_id, db)
    if plan is None:
        raise HTTPException(status_code=404, detail="No hay plan generado.")
    return _estado_out(plan, await _count_versions(plan, db))


@router.post("/annual-plan/roadmap/validar")
async def validar_roadmap(
    user_id: str = Depends(get_current_user_id), db: AsyncSession = Depends(get_db),
):
    """Sella el roadmap: queda solo lectura, se archiva como versión inmutable y se
    registra como tema de la próxima sesión del consejo."""
    plan = await _current_plan(user_id, db)
    if plan is None:
        raise HTTPException(status_code=404, detail="No hay plan generado.")
    if not plan.roadmap:
        raise HTTPException(status_code=409, detail="Aún no hay roadmap que validar.")

    validated_at = datetime.now(timezone.utc)
    plan.roadmap_status = "validado"
    plan.roadmap_validated_at = validated_at

    # Lo registra en la agenda del consejo (tema permanente hasta que lo revisen).
    existentes = (await db.execute(
        select(BoardTheme).where(
            BoardTheme.annual_plan_id == plan.id, BoardTheme.key == _ROADMAP_THEME_KEY)
    )).scalars().all()
    if existentes:
        for t in existentes:
            t.active = True
    else:
        db.add(BoardTheme(
            annual_plan_id=plan.id, key=_ROADMAP_THEME_KEY, label=_ROADMAP_THEME_LABEL,
            type="permanente", every_n_sessions=1, active=True, is_default=False, order_index=0,
        ))

    # Archiva el snapshot: copia profunda, para que editar el roadmap después
    # (tras reabrirlo) nunca toque la versión ya validada.
    version = await _count_versions(plan, db) + 1
    db.add(RoadmapVersion(
        user_id=user_id, plan_id=plan.id, version=version,
        roadmap=copy.deepcopy(plan.roadmap), validated_at=validated_at,
    ))

    await db.commit()
    return _estado_out(plan, version)


@router.post("/annual-plan/roadmap/reabrir")
async def reabrir_roadmap(
    user_id: str = Depends(get_current_user_id), db: AsyncSession = Depends(get_db),
):
    """Regresa el roadmap a borrador (editable) y lo retira de la agenda del consejo.
    Las versiones ya validadas NO se borran: quedan archivadas en la Biblioteca."""
    plan = await _current_plan(user_id, db)
    if plan is None:
        raise HTTPException(status_code=404, detail="No hay plan generado.")
    plan.roadmap_status = "borrador"
    plan.roadmap_validated_at = None
    temas = (await db.execute(
        select(BoardTheme).where(
            BoardTheme.annual_plan_id == plan.id, BoardTheme.key == _ROADMAP_THEME_KEY)
    )).scalars().all()
    for t in temas:
        t.active = False
    await db.commit()
    return _estado_out(plan, await _count_versions(plan, db))


async def _pdf_branding(user_id: str, db: AsyncSession) -> tuple[str | None, bytes | None]:
    onb = (await db.execute(
        select(OnboardingSession).where(OnboardingSession.user_id == user_id)
        .order_by(OnboardingSession.created_at.desc())
    )).scalars().first()
    company_name = (((onb.memory_buffer if onb else {}) or {}).get("company") or {}).get("name")
    logo = await get_logo_bytes(user_id, db)
    return company_name, logo


@router.get("/annual-plan/roadmap/pdf")
async def roadmap_pdf(
    user_id: str = Depends(get_current_user_id), db: AsyncSession = Depends(get_db),
):
    plan = await _current_plan(user_id, db)
    if plan is None or not plan.roadmap:
        raise HTTPException(status_code=404, detail="No hay roadmap disponible.")
    company_name, logo = await _pdf_branding(user_id, db)
    from app.services.pdf.roadmap_pdf import build_roadmap_pdf
    pdf = await anyio.to_thread.run_sync(lambda: build_roadmap_pdf(plan.roadmap, company_name, logo))
    return Response(content=pdf, media_type="application/pdf",
                    headers={"Content-Disposition": 'attachment; filename="roadmap.pdf"'})


# ── Versiones archivadas del roadmap ─────────────────────────────────────────

@router.get("/annual-plan/roadmap/versiones")
async def list_roadmap_versiones(
    user_id: str = Depends(get_current_user_id), db: AsyncSession = Depends(get_db),
):
    """Las versiones validadas del roadmap, de la más reciente a la más antigua."""
    versiones = (await db.execute(
        select(RoadmapVersion)
        .where(RoadmapVersion.user_id == user_id)
        .order_by(RoadmapVersion.version.desc())
    )).scalars().all()
    return [
        {"id": str(v.id), "version": v.version, "validated_at": v.validated_at}
        for v in versiones
    ]


@router.get("/annual-plan/roadmap/versiones/{version_id}/pdf")
async def roadmap_version_pdf(
    version_id: uuid.UUID,
    user_id: str = Depends(get_current_user_id), db: AsyncSession = Depends(get_db),
):
    """El PDF de una versión archivada: se construye con SU snapshot, no con el roadmap actual."""
    version = (await db.execute(
        select(RoadmapVersion).where(
            RoadmapVersion.id == version_id, RoadmapVersion.user_id == user_id)
    )).scalar_one_or_none()
    if version is None:
        raise HTTPException(status_code=404, detail="Versión no encontrada.")
    company_name, logo = await _pdf_branding(user_id, db)
    from app.services.pdf.roadmap_pdf import build_roadmap_pdf
    snapshot = version.roadmap or {}
    pdf = await anyio.to_thread.run_sync(lambda: build_roadmap_pdf(snapshot, company_name, logo))
    return Response(
        content=pdf, media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="roadmap-v{version.version}.pdf"'},
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

    selected_docs: list[dict] = []
    docs_note = ""
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
        evidence_counts = {}
        if tasks:
            task_ids = [t.id for t in tasks]
            cres = await db.execute(
                select(Evidence.action_task_id, func.count())
                .where(Evidence.action_task_id.in_(task_ids))
                .group_by(Evidence.action_task_id)
            )
            evidence_counts = {str(tid): cnt for tid, cnt in cres.all()}
            eres = await db.execute(
                select(Evidence).where(Evidence.action_task_id.in_(task_ids)).order_by(Evidence.created_at)
            )
            evidences = list(eres.scalars().all())
            tasks_by_id = {str(t.id): t for t in tasks}
            selected_docs, docs_note = select_review_documents(evidences, tasks_by_id)
        signals = compute_signals(tasks, kpis, memory_buffer, today, evidence_counts=evidence_counts)

    review_documents: list[dict] = []
    for d in selected_docs:
        raw = download_from_storage(d["s3_key"])
        if raw is None:
            continue
        review_documents.append({
            "kind": d["kind"], "media_type": d["media_type"],
            "data": base64.b64encode(raw).decode("ascii"), "label": d["label"],
        })

    review = await anyio.to_thread.run_sync(
        lambda: run_month_review(
            signals=signals, month_focus=focus, objectives=objectives,
            memory_buffer=memory_buffer, period_label=period_label,
            incomplete_task_ids=incomplete_ids,
            documents=review_documents, documents_note=docs_note,
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
        plan = await db.get(AnnualPlan, annual_plan_id)
        horizon_years = (plan.horizon_years or 1) if plan else 1
        await db.commit()

    total_months = horizon_years * 12
    active_idx = month_index + 1 if month_index < total_months else month_index
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


async def _build_orden_data(plan, month_index: int, db: AsyncSession) -> dict | None:
    res = await db.execute(select(BoardTheme).where(BoardTheme.annual_plan_id == plan.id))
    themes = list(res.scalars().all())
    mres = await db.execute(
        select(MonthlyPlan)
        .where(MonthlyPlan.annual_plan_id == plan.id, MonthlyPlan.month_index == month_index)
        .options(selectinload(MonthlyPlan.objectives))
    )
    month = mres.scalar_one_or_none()
    if not month:
        return None
    sched = scheduled_for_session(themes, month_index)
    grouped = await _tasks_by_objective([o.id for o in month.objectives], db)
    return {
        "month_index": month.month_index,
        "period_year": month.period_year,
        "period_month": month.period_month,
        "permanent_themes": [_theme_ref(t) for t in sched["permanente"]],
        "coverage_themes": [_theme_ref(t) for t in sched["cobertura"]],
        "covered_keys": list(month.covered_themes or []),
        "objectives": [_objective_out(o, grouped.get(o.id, [])) for o in month.objectives],
    }


@router.get("/annual-plan/months/{month_index}/orden-del-dia", response_model=OrdenDelDiaOut)
async def get_orden_del_dia(
    month_index: int,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    plan = await _current_plan(user_id, db)
    if not plan:
        raise HTTPException(status_code=404, detail="No hay plan generado.")
    data = await _build_orden_data(plan, month_index, db)
    if data is None:
        raise HTTPException(status_code=404, detail="Mes no encontrado.")
    return OrdenDelDiaOut(**data)


@router.get("/annual-plan/months/{month_index}/orden-del-dia/pdf")
async def get_orden_del_dia_pdf(
    month_index: int,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    plan = await _current_plan(user_id, db)
    if not plan:
        raise HTTPException(status_code=404, detail="No hay plan generado.")
    data = await _build_orden_data(plan, month_index, db)
    if data is None:
        raise HTTPException(status_code=404, detail="Mes no encontrado.")
    data["period_label"] = f"{_MONTH_NAMES[data['period_month']]} {data['period_year']}"

    company_name = None
    try:
        onb = await db.execute(
            select(OnboardingSession).where(OnboardingSession.user_id == user_id)
            .order_by(OnboardingSession.created_at.desc()).limit(1)
        )
        onboarding = onb.scalar_one_or_none()
        mb = (onboarding.memory_buffer if onboarding else {}) or {}
        company_name = (mb.get("company") or {}).get("name")
    except Exception:
        company_name = None

    logo = await get_logo_bytes(user_id, db)
    pdf = build_orden_pdf(data, company_name, logo)
    return Response(
        content=pdf, media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="orden-del-dia-mes-{month_index}.pdf"'},
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
    active = compute_active_month_index(plan.start_date, date.today(), total_months=(plan.horizon_years or 1) * 12)
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
    active = compute_active_month_index(plan.start_date, date.today(), total_months=(plan.horizon_years or 1) * 12)
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


# ── Alertas (B6) ──────────────────────────────────────────────────────────────

@router.get("/annual-plan/alertas", response_model=list[AlertItem])
async def get_alertas(
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    plan = await _current_plan(user_id, db)
    if not plan:
        raise HTTPException(status_code=404, detail="No hay plan generado.")

    mres = await db.execute(
        select(MonthlyPlan)
        .where(MonthlyPlan.annual_plan_id == plan.id)
        .options(selectinload(MonthlyPlan.objectives))
    )
    months = list(mres.scalars().all())
    obj_ids = [o.id for m in months for o in m.objectives]
    grouped = await _tasks_by_objective(obj_ids, db)
    tasks = [t for ts in grouped.values() for t in ts]

    tres = await db.execute(select(BoardTheme).where(BoardTheme.annual_plan_id == plan.id))
    themes = list(tres.scalars().all())
    active = compute_active_month_index(plan.start_date, date.today(), total_months=(plan.horizon_years or 1) * 12)
    rows = coverage_rows(themes, months, active)

    kpi_signals: list = []
    done = [m for m in months if m.status == "done" and m.review]
    if done:
        latest = max(done, key=lambda m: m.month_index)
        kpi_signals = ((latest.review or {}).get("signals") or {}).get("kpis") or []

    alerts = compute_alerts(tasks, rows, kpi_signals, date.today())
    ra = review_alert(months)
    alerts = ([ra] if ra else []) + alerts
    return [AlertItem(**a) for a in alerts]


# ── Agenda del mes (Motor de Orden del Día por señales) ───────────────────────

async def _agenda_estado(plan, db: AsyncSession):
    """Reúne el EstadoMes en vivo y devuelve (agenda_determinista, months, active, active_month)."""
    mres = await db.execute(
        select(MonthlyPlan)
        .where(MonthlyPlan.annual_plan_id == plan.id)
        .options(selectinload(MonthlyPlan.objectives))
    )
    months = list(mres.scalars().all())
    obj_ids = [o.id for m in months for o in m.objectives]
    grouped = await _tasks_by_objective(obj_ids, db)
    tasks = [t for ts in grouped.values() for t in ts]

    tres = await db.execute(select(BoardTheme).where(BoardTheme.annual_plan_id == plan.id))
    themes = list(tres.scalars().all())
    active = compute_active_month_index(plan.start_date, date.today(), total_months=(plan.horizon_years or 1) * 12)
    sched = scheduled_for_session(themes, active)
    scheduled_themes = list(sched["permanente"]) + list(sched["cobertura"])
    rows = coverage_rows(themes, months, active)

    kpi_signals: list = []
    done = [m for m in months if m.status == "done" and m.review]
    if done:
        latest = max(done, key=lambda m: m.month_index)
        kpi_signals = ((latest.review or {}).get("signals") or {}).get("kpis") or []

    agenda = build_agenda(scheduled_themes, rows, kpi_signals, tasks, date.today())
    active_month = next((m for m in months if m.month_index == active), None)
    return agenda, months, active, active_month


@router.get("/annual-plan/agenda", response_model=AgendaOut)
async def get_agenda(
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    plan = await _current_plan(user_id, db)
    if not plan:
        raise HTTPException(status_code=404, detail="No hay plan generado.")
    agenda, _months, _active, active_month = await _agenda_estado(plan, db)
    if active_month is not None and active_month.chair_agenda:
        ca = active_month.chair_agenda
        return AgendaOut(curada=True, carta=ca.get("carta", ""), items=ca.get("items", []))
    return AgendaOut(curada=False, carta="", items=agenda)


@router.post("/annual-plan/agenda/chair", response_model=AgendaOut)
async def convocar_chair(
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    plan = await _current_plan(user_id, db)
    if not plan:
        raise HTTPException(status_code=404, detail="No hay plan generado.")
    agenda, _months, _active, active_month = await _agenda_estado(plan, db)

    period_label = (
        f"{_MONTH_NAMES[active_month.period_month]} {active_month.period_year}"
        if active_month is not None else ""
    )
    memory_buffer: dict = {}
    try:
        onb = await db.execute(
            select(OnboardingSession).where(OnboardingSession.user_id == user_id)
            .order_by(OnboardingSession.created_at.desc()).limit(1)
        )
        onboarding = onb.scalar_one_or_none()
        memory_buffer = (onboarding.memory_buffer if onboarding else {}) or {}
    except Exception:
        memory_buffer = {}

    result = await anyio.to_thread.run_sync(chair_curate_agenda, agenda, memory_buffer, period_label)

    if active_month is not None:
        active_month.chair_agenda = {
            "carta": result["carta"], "items": result["items"],
            "generated_at": date.today().isoformat(),
        }
        _flag_modified(active_month, "chair_agenda")

    return AgendaOut(curada=True, carta=result["carta"], items=result["items"])


async def _active_month(plan, db: AsyncSession):
    """Devuelve el MonthlyPlan del mes activo (sin construir la agenda)."""
    res = await db.execute(select(MonthlyPlan).where(MonthlyPlan.annual_plan_id == plan.id))
    months = list(res.scalars().all())
    active = compute_active_month_index(plan.start_date, date.today(), total_months=(plan.horizon_years or 1) * 12)
    return next((m for m in months if m.month_index == active), None)


# ── Minuta (nodo 5) ───────────────────────────────────────────────────────────

@router.post("/annual-plan/minuta", response_model=MinutaOut)
async def generar_minuta(
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    plan = await _current_plan(user_id, db)
    if not plan:
        raise HTTPException(status_code=404, detail="No hay plan generado.")
    agenda, _months, _active, active_month = await _agenda_estado(plan, db)
    items = (
        active_month.chair_agenda["items"]
        if (active_month is not None and active_month.chair_agenda) else agenda
    )
    period_label = (
        f"{_MONTH_NAMES[active_month.period_month]} {active_month.period_year}"
        if active_month is not None else ""
    )
    memory_buffer: dict = {}
    try:
        onb = await db.execute(
            select(OnboardingSession).where(OnboardingSession.user_id == user_id)
            .order_by(OnboardingSession.created_at.desc()).limit(1)
        )
        onboarding = onb.scalar_one_or_none()
        memory_buffer = (onboarding.memory_buffer if onboarding else {}) or {}
    except Exception:
        memory_buffer = {}

    result = await anyio.to_thread.run_sync(generate_minuta, items, memory_buffer, period_label)

    if active_month is not None:
        active_month.minuta = {
            "carta": result["carta"], "temas": result["temas"],
            "generated_at": date.today().isoformat(),
        }
        _flag_modified(active_month, "minuta")

    return MinutaOut(generada=True, carta=result["carta"], temas=result["temas"])


@router.get("/annual-plan/minuta", response_model=MinutaOut)
async def get_minuta(
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    plan = await _current_plan(user_id, db)
    if not plan:
        raise HTTPException(status_code=404, detail="No hay plan generado.")
    active_month = await _active_month(plan, db)
    if active_month is not None and active_month.minuta:
        m = active_month.minuta
        return MinutaOut(generada=True, carta=m.get("carta", ""), temas=m.get("temas", []))
    return MinutaOut(generada=False, carta="", temas=[])


@router.post("/annual-plan/minuta/decision", response_model=MinutaOut)
async def cerrar_decision(
    body: DecisionIn,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    if body.decision not in ("A", "B", "aplazar"):
        raise HTTPException(status_code=422, detail="Decisión inválida.")
    plan = await _current_plan(user_id, db)
    if not plan:
        raise HTTPException(status_code=404, detail="No hay plan generado.")
    active_month = await _active_month(plan, db)
    if active_month is None or not active_month.minuta:
        raise HTTPException(status_code=404, detail="Minuta no encontrada.")

    minuta = dict(active_month.minuta)
    temas = minuta.get("temas", [])
    tema = next((t for t in temas if t.get("id") == body.tema_id), None)
    if tema is None:
        raise HTTPException(status_code=404, detail="Tema no encontrado.")

    tema["decision"]["decision_tomada"] = body.decision
    if body.decision in ("A", "B"):
        opcion = tema["decision"]["opcion_a"] if body.decision == "A" else tema["decision"]["opcion_b"]
        fecha = date.today() + timedelta(days=14)
        comp = Compromiso(
            user_id=user_id, descripcion=opcion, fecha_compromiso=fecha,
            status="abierto", token=secrets.token_urlsafe(16), avances=[],
            source={"month_id": str(active_month.id), "tema_id": body.tema_id},
        )
        db.add(comp)
        await db.flush()
        tema["compromiso"] = {
            "descripcion": opcion, "fecha": fecha.isoformat(), "compromiso_id": str(comp.id),
        }
    else:
        tema["compromiso"] = None

    active_month.minuta = minuta
    _flag_modified(active_month, "minuta")
    return MinutaOut(generada=True, carta=minuta.get("carta", ""), temas=temas)
