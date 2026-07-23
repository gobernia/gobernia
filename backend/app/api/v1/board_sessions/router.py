"""
Etapa 9 — BoardSession: sesiones de consejo recurrentes con agentes IA.

POST   /board-sessions                        → crear sesión del periodo
GET    /board-sessions                        → listar sesiones del usuario
GET    /board-sessions/{id}                   → detalle + mensajes
POST   /board-sessions/{id}/kpis             → ingresar KPIs del periodo
POST   /board-sessions/{id}/analyse          → trigger análisis de los 4 agentes
POST   /board-sessions/{id}/chat             → enviar mensaje a un agente
GET    /board-sessions/{id}/chat             → historial del chat
"""
import base64
import logging
import secrets
import uuid
from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import delete, select
from sqlalchemy.orm import selectinload

from app.services.data_completeness import missing_company_data
from app.core.dependencies import get_current_user_id, get_db
from app.models.action_plan import ActionTask
from app.models.annual_plan import AnnualPlan, MonthlyPlan
from app.models.board_session import BoardSession
from app.models.chat_message import ChatMessage
from app.models.compromiso import Compromiso
from app.models.document import Document
from app.models.onboarding_session import OnboardingSession
from app.services.ai.agents.deliberacion import run_deliberacion
from app.services.ai.annual_plan_generator import compute_active_month_index
from app.schemas.board_session import (
    AnalysisRequest,
    BoardSessionCreate,
    BoardSessionDetail,
    BoardSessionKPIsInput,
    BoardSessionSummary,
    ChatMessageInput,
    ChatMessageOut,
    normalize_agent_analyses,
)
from app.schemas.etapa7 import DOCUMENT_TYPE_LABELS
from app.services.ai.agents.base import (
    AGENT_DOC_TYPES,
    failed_agent_analysis,
    run_agent_analysis,
    run_agent_chat,
    run_agent_chat_stream,
    run_challenger_critique,
    run_agent_revision,
)
from app.services.ai.doc_blocks import classify_docs, select_for_agent
from app.services.documents.storage import download_from_storage
from app.api.v1.board_sessions.documents import router as documents_router

_log = logging.getLogger(__name__)

router = APIRouter(prefix="/board-sessions", tags=["board-sessions"])
router.include_router(documents_router)

# Nota que recibe el agente cuando su análisis con documentos falló y se reintenta sin ellos.
_NOTA_SIN_DOCUMENTOS = (
    "No pude abrir los documentos de esta sesión (pueden estar dañados, protegidos con "
    "contraseña o ser demasiado extensos). Analiza solo con el contexto y los KPIs, deja "
    "todas las `fuente` vacías y pídele al dueño que los vuelva a subir en PDF válido."
)

_MONTH_NAMES = [
    "", "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
    "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre",
]
VALID_AGENTS = {"CFO", "CSO", "CRO", "Auditor"}

# Cómo se lee cada estatus Kanban en el bloque de AVANCE que ve el Consejo.
_STATUS_LABEL = {
    "completada": "completada",
    "en_progreso": "en proceso",
    "pendiente": "sin ejecutar",
}


def _format_avance_tareas(months, tasks_by_obj: dict, active_index: int) -> str | None:
    """
    Bloque de texto 'AVANCE DEL PLAN' para la deliberación: totales de cumplimiento
    (hechas / en proceso / sin ejecutar) + el detalle de las tareas del periodo actual y las
    incompletas arrastradas de meses anteriores. Devuelve None si el plan no tiene tareas.
    """
    all_tasks = [t for m in months for o in m.objectives for t in tasks_by_obj.get(o.id, [])]
    if not all_tasks:
        return None

    hechas = sum(1 for t in all_tasks if t.status == "completada")
    en_proceso = sum(1 for t in all_tasks if t.status == "en_progreso")
    sin_ejecutar = len(all_tasks) - hechas - en_proceso

    def _line(t, sufijo: str = "") -> str:
        estado = _STATUS_LABEL.get(t.status, t.status)
        resp = f" (resp. {t.owner})" if t.owner else ""
        return f"  - [{estado}] {t.title}{resp}{sufijo}"

    lines = [
        f"Totales del plan: {hechas} completada(s), {en_proceso} en proceso, "
        f"{sin_ejecutar} sin ejecutar (de {len(all_tasks)} tareas)."
    ]

    actual = next((m for m in months if m.month_index == active_index), None)
    if actual is not None:
        actual_tasks = [t for o in actual.objectives for t in tasks_by_obj.get(o.id, [])]
        label = f"{_MONTH_NAMES[actual.period_month]} {actual.period_year}"
        lines.append(f"\nTareas del periodo actual ({label}):")
        lines.extend(_line(t) for t in actual_tasks) if actual_tasks else \
            lines.append("  (sin tareas asignadas a este mes)")

    arrastradas = [
        (m, t)
        for m in months if m.month_index < active_index
        for o in m.objectives for t in tasks_by_obj.get(o.id, [])
        if t.status != "completada"
    ]
    if arrastradas:
        lines.append("\nTareas arrastradas de meses anteriores (incompletas):")
        for m, t in arrastradas:
            origen = f"{_MONTH_NAMES[m.period_month]} {m.period_year}"
            lines.append(_line(t, sufijo=f" — viene de {origen}"))

    return "\n".join(lines)


def _format_acuerdos_previos(rows, today: date) -> str | None:
    """Bloque 'ACUERDOS PENDIENTES DE SESIONES ANTERIORES': descripción, responsable, fecha y si
    está vencido. Devuelve None si no hay acuerdos abiertos que arrastrar."""
    if not rows:
        return None
    lines = []
    for c in rows:
        resp = c.responsable_nombre or "(sin responsable asignado)"
        if c.fecha_compromiso:
            fecha = c.fecha_compromiso.isoformat()
            vencido = " — VENCIDO" if c.fecha_compromiso < today else ""
        else:
            fecha, vencido = "(sin fecha)", ""
        lines.append(
            f"  - {c.descripcion} · resp. {resp} · fecha {fecha} · estatus «{c.status}»{vencido}"
        )
    return "\n".join(lines)


async def _get_onboarding_or_404(
    user_id: str, db: AsyncSession
) -> OnboardingSession:
    result = await db.execute(
        select(OnboardingSession)
        .where(OnboardingSession.user_id == user_id)
        .order_by(OnboardingSession.created_at.desc())
    )
    session = result.scalars().first()
    if not session:
        raise HTTPException(status_code=404, detail="Perfil de empresa no encontrado. Completa el onboarding primero.")
    if 8 not in (session.completed_stages or []):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Debes completar el onboarding antes de crear una sesión de consejo.",
        )
    faltantes = missing_company_data(session.memory_buffer)
    if faltantes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Faltan datos de tu empresa: " + "; ".join(faltantes)
            + ". Complétalos en la sección Datos antes de crear una sesión de consejo.",
        )
    return session


async def _get_board_session_or_404(
    board_session_id: uuid.UUID, user_id: str, db: AsyncSession
) -> BoardSession:
    result = await db.execute(
        select(BoardSession)
        .where(
            BoardSession.id == board_session_id,
            BoardSession.user_id == user_id,
        )
        .options(selectinload(BoardSession.messages), selectinload(BoardSession.documents))
    )
    bs = result.scalar_one_or_none()
    if not bs:
        raise HTTPException(status_code=404, detail="Sesión de consejo no encontrada.")
    return bs


# ── POST /board-sessions ──────────────────────────────────────────────────────

@router.post("", response_model=BoardSessionSummary, status_code=status.HTTP_201_CREATED)
async def create_board_session(
    body: BoardSessionCreate,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Crea una nueva sesión de consejo para el periodo indicado."""
    onboarding = await _get_onboarding_or_404(user_id, db)

    # Verificar que no exista ya una sesión para ese periodo
    existing = await db.execute(
        select(BoardSession).where(
            BoardSession.onboarding_session_id == onboarding.id,
            BoardSession.period_year == body.period_year,
            BoardSession.period_month == body.period_month,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Ya existe una sesión para {_MONTH_NAMES[body.period_month]} {body.period_year}.",
        )

    bs = BoardSession(
        onboarding_session_id=onboarding.id,
        user_id=user_id,
        period_year=body.period_year,
        period_month=body.period_month,
        status="draft",
        profile_snapshot=dict(onboarding.memory_buffer or {}),
        governance_score_snapshot=onboarding.governance_score,
    )
    db.add(bs)
    await db.flush()
    await db.commit()

    return BoardSessionSummary(
        board_session_id=str(bs.id),
        onboarding_session_id=str(onboarding.id),
        period_year=bs.period_year,
        period_month=bs.period_month,
        period_label=f"{_MONTH_NAMES[bs.period_month]} {bs.period_year}",
        status=bs.status,
        governance_score_snapshot=bs.governance_score_snapshot,
        document_count=0,
        message_count=0,
        created_at=bs.created_at or datetime.now(timezone.utc),
    )


# ── GET /board-sessions ───────────────────────────────────────────────────────

@router.get("", response_model=list[BoardSessionSummary])
async def list_board_sessions(
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Lista todas las sesiones de consejo del usuario, más recientes primero."""
    result = await db.execute(
        select(BoardSession)
        .where(BoardSession.user_id == user_id)
        .order_by(BoardSession.period_year.desc(), BoardSession.period_month.desc())
        .options(selectinload(BoardSession.messages), selectinload(BoardSession.documents))
    )
    sessions = result.scalars().all()
    return [
        BoardSessionSummary(
            board_session_id=str(bs.id),
            onboarding_session_id=str(bs.onboarding_session_id),
            period_year=bs.period_year,
            period_month=bs.period_month,
            period_label=f"{_MONTH_NAMES[bs.period_month]} {bs.period_year}",
            status=bs.status,
            governance_score_snapshot=bs.governance_score_snapshot,
            document_count=len(bs.documents) if bs.documents else 0,
            message_count=len(bs.messages) if bs.messages else 0,
            created_at=bs.created_at,
        )
        for bs in sessions
    ]


# ── GET /board-sessions/{id} ──────────────────────────────────────────────────

@router.get("/{board_session_id}", response_model=BoardSessionDetail)
async def get_board_session(
    board_session_id: uuid.UUID,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Retorna el detalle completo de una sesión incluyendo análisis y mensajes."""
    bs = await _get_board_session_or_404(board_session_id, user_id, db)
    messages = [
        ChatMessageOut(
            message_id=str(m.id),
            role=m.role,
            agent=m.agent,
            content=m.content,
            created_at=m.created_at,
        )
        for m in (bs.messages or [])
    ]
    return BoardSessionDetail(
        board_session_id=str(bs.id),
        onboarding_session_id=str(bs.onboarding_session_id),
        period_year=bs.period_year,
        period_month=bs.period_month,
        period_label=f"{_MONTH_NAMES[bs.period_month]} {bs.period_year}",
        status=bs.status,
        kpi_snapshot=bs.kpi_snapshot,
        agent_analyses=normalize_agent_analyses(bs.agent_analyses),
        conclusion=await _conclusion_out(db, bs),
        governance_score_snapshot=bs.governance_score_snapshot,
        messages=messages,
        created_at=bs.created_at,
        completed_at=bs.completed_at,
    )


# ── POST /board-sessions/{id}/kpis ────────────────────────────────────────────

@router.post("/{board_session_id}/kpis")
async def submit_period_kpis(
    board_session_id: uuid.UUID,
    body: BoardSessionKPIsInput,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Guarda los KPIs del periodo en el snapshot de la sesión."""
    bs = await _get_board_session_or_404(board_session_id, user_id, db)

    # Obtener perfil base para templates
    onboarding_result = await db.execute(
        select(OnboardingSession).where(OnboardingSession.id == bs.onboarding_session_id)
    )
    onboarding = onboarding_result.scalar_one_or_none()
    buf = onboarding.memory_buffer if onboarding else {}

    from app.services.ai.kpi_engine import build_kpi_templates, process_kpi_values
    templates = build_kpi_templates(buf)
    results, alerts = process_kpi_values(templates, body.kpis, buf)

    from app.services.ai.kpi_engine import build_etapa5_memory
    bs.kpi_snapshot = build_etapa5_memory(results, alerts)
    bs.status = "active"

    await db.flush()
    await db.commit()

    return {
        "board_session_id": str(bs.id),
        "kpi_count": len(results),
        "alert_count": len(alerts),
        "alerts": alerts,
        "status": bs.status,
    }


async def _conclusion_out(db: AsyncSession, bs: BoardSession) -> dict | None:
    """
    La conclusión del Consejo, con sus acuerdos hidratados desde los `Compromiso` reales
    (id, responsable y estatus vivos), no desde el texto que produjo la IA: el dueño edita
    esos compromisos y la pantalla debe mostrar lo que hay hoy, no lo que se acordó ayer.
    """
    if not bs.conclusion:
        return None
    rows = (await db.execute(
        select(Compromiso)
        .where(Compromiso.board_session_id == bs.id)
        .order_by(Compromiso.created_at)
    )).scalars().all()
    acuerdos = [
        {
            "id": str(c.id),
            "texto": c.descripcion,
            "responsable_sugerido": c.responsable_nombre or "",
            "responsable_nombre": c.responsable_nombre,
            "responsable_email": c.responsable_email,
            "fecha_compromiso": c.fecha_compromiso.isoformat() if c.fecha_compromiso else None,
            "prioridad": c.prioridad,
            "pilar": c.pilar or "",
            "racional": c.racional or "",
            "status": c.status,
        }
        for c in rows
    ]
    return {**bs.conclusion, "acuerdos": acuerdos}


# ── POST /board-sessions/{id}/analyse ────────────────────────────────────────

@router.post("/{board_session_id}/analyse")
async def run_analyses(
    board_session_id: uuid.UUID,
    body: AnalysisRequest,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Ejecuta el análisis de los agentes solicitados con el contexto del periodo."""
    bs = await _get_board_session_or_404(board_session_id, user_id, db)

    invalid = set(body.agents) - VALID_AGENTS
    if invalid:
        raise HTTPException(status_code=400, detail=f"Agentes no válidos: {', '.join(invalid)}")

    # Obtener perfil base
    onboarding_result = await db.execute(
        select(OnboardingSession).where(OnboardingSession.id == bs.onboarding_session_id)
    )
    onboarding = onboarding_result.scalar_one_or_none()
    memory_buffer = onboarding.memory_buffer if onboarding else {}

    # Historial de análisis anteriores para contexto
    history_result = await db.execute(
        select(BoardSession)
        .where(
            BoardSession.onboarding_session_id == bs.onboarding_session_id,
            BoardSession.id != bs.id,
            BoardSession.agent_analyses.isnot(None),
        )
        .order_by(BoardSession.period_year.desc(), BoardSession.period_month.desc())
        .limit(3)
    )
    past_sessions = history_result.scalars().all()
    previous_analyses = [
        {
            "period": f"{_MONTH_NAMES[s.period_month]} {s.period_year}",
            "summary": (s.agent_analyses or {}).get(agent, {}).get("summary", ""),
        }
        for s in past_sessions
        for agent in body.agents
        if (s.agent_analyses or {}).get(agent)
    ]

    # Board pack de la sesión: se lee ANTES de cerrar la conexión (la descarga de los
    # bytes va después, ya sin DB abierta).
    docs_result = await db.execute(
        select(Document)
        .where(Document.board_session_id == bs.id)
        .order_by(Document.created_at.desc())
    )
    board_docs = [
        {
            "s3_key": d.s3_key,
            "filename": d.filename,
            "document_type": d.document_type,
            "label": (
                f"Documento «{d.filename}» "
                f"({DOCUMENT_TYPE_LABELS.get(d.document_type, d.document_type)}) "
                "subido para esta sesión de consejo."
            ),
        }
        for d in docs_result.scalars().all()
    ]
    # Se clasifican aquí, pero los topes (nº de documentos y bytes) y la nota se aplican
    # POR AGENTE, después del ruteo: si no, 8 láminas de hoy dejan al CFO sin el estado
    # financiero de ayer, y el CSO recibe avisos sobre documentos que no son de su competencia.
    readable_board_docs, unreadable_board_docs = classify_docs(board_docs)

    # El ROADMAP es el documento rector: el Consejo evalúa a la empresa CONTRA su plan,
    # no en abstracto. Se lee aquí (antes de cerrar la conexión) y se pasa a cada consejero.
    plan_result = await db.execute(
        select(AnnualPlan)
        .where(AnnualPlan.user_id == user_id, AnnualPlan.status == "active")
        .order_by(AnnualPlan.created_at.desc())
        .limit(1)
    )
    plan = plan_result.scalar_one_or_none()
    roadmap = dict(plan.roadmap) if (plan and plan.roadmap) else None
    if roadmap is not None:
        # El agente debe saber si lo lee en firme o si el dueño aún lo está revisando.
        roadmap["_status"] = getattr(plan, "roadmap_status", "borrador")

    # AVANCE DEL PLAN: el Consejo evalúa cómo van las tareas, no solo los documentos. Se carga
    # aquí (antes de cerrar la conexión) y se pasa a la deliberación como bloque de texto.
    avance_tareas: str | None = None
    if plan is not None:
        mres = await db.execute(
            select(MonthlyPlan)
            .where(MonthlyPlan.annual_plan_id == plan.id)
            .order_by(MonthlyPlan.month_index)
            .options(selectinload(MonthlyPlan.objectives))
        )
        plan_months = list(mres.scalars().all())
        plan_obj_ids = [o.id for m in plan_months for o in m.objectives]
        tasks_by_obj: dict = {}
        if plan_obj_ids:
            tres = await db.execute(
                select(ActionTask)
                .where(ActionTask.objective_id.in_(plan_obj_ids))
                .order_by(ActionTask.order_index)
            )
            for t in tres.scalars().all():
                tasks_by_obj.setdefault(t.objective_id, []).append(t)
        active_index = compute_active_month_index(
            plan.start_date, date.today(), total_months=(plan.horizon_years or 1) * 12
        )
        avance_tareas = _format_avance_tareas(plan_months, tasks_by_obj, active_index)

    # CONTINUIDAD: la sesión arrastra los acuerdos ABIERTOS de las sesiones anteriores del usuario.
    # Aquí NO se tocan (la gestión real vive en el módulo pm): solo se le dan al Consejo como
    # contexto para que revise su cumplimiento y decida si los mantiene, reprograma o cierra.
    prev_rows = (await db.execute(
        select(Compromiso).where(
            Compromiso.user_id == user_id,
            Compromiso.board_session_id.isnot(None),
            Compromiso.board_session_id != bs.id,
            Compromiso.status.notin_(["completado", "cerrado"]),
        ).order_by(Compromiso.created_at)
    )).scalars().all()
    acuerdos_previos = _format_acuerdos_previos(prev_rows, date.today())

    # Snapshot de campos necesarios y liberar la conexión a DB ANTES de los LLM calls.
    # Las 12 llamadas a Claude (4 agentes × 3 fases) pueden tomar minutos; mantener la
    # conexión abierta dispara el statement timeout de Supabase (QueryCanceledError).
    kpi_snapshot = bs.kpi_snapshot
    period_year  = bs.period_year
    period_month = bs.period_month
    analyses  = dict(bs.agent_analyses or {})
    critiques = dict(bs.agent_critiques or {})
    bs_id     = bs.id
    await db.commit()
    await db.close()

    # Descargar los bytes de los documentos legibles. Si uno falla, se ignora (no rompe la sesión).
    import anyio
    ready_docs: list[dict] = []
    for d in readable_board_docs:
        raw = await anyio.to_thread.run_sync(lambda k=d["s3_key"]: download_from_storage(k))
        if raw is None:
            continue
        ready_docs.append({
            "filename": d["filename"],
            "document_type": d["document_type"],
            "kind": d["kind"],
            "media_type": d["media_type"],
            "size_bytes": len(raw),
            "data": base64.b64encode(raw).decode("ascii"),
            "label": d["label"],
        })

    async def _pipeline(agent: str, docs: list[dict], note: str) -> tuple[dict, dict]:
        """Análisis inicial → crítica del Challenger → revisión, para UN agente."""
        initial = await anyio.to_thread.run_sync(
            lambda: run_agent_analysis(
                agent=agent,
                memory_buffer=memory_buffer,
                kpi_snapshot=kpi_snapshot,
                period_year=period_year,
                period_month=period_month,
                previous_analyses=previous_analyses,
                documents=docs,
                documents_note=note,
                roadmap=roadmap,
            )
        )
        critique = await anyio.to_thread.run_sync(
            lambda: run_challenger_critique(
                agent=agent,
                initial_analysis=initial,
                memory_buffer=memory_buffer,
                kpi_snapshot=kpi_snapshot,
                period_year=period_year,
                period_month=period_month,
            )
        )
        revised = await anyio.to_thread.run_sync(
            lambda: run_agent_revision(
                agent=agent,
                initial_analysis=initial,
                critique=critique,
                memory_buffer=memory_buffer,
                kpi_snapshot=kpi_snapshot,
                period_year=period_year,
                period_month=period_month,
                previous_analyses=previous_analyses,
            )
        )
        return revised, critique

    # Ejecutar el pipeline por agente. Sin conexión a DB activa; las llamadas son sync pero
    # el event loop sigue libre para otras requests.
    # Un agente que revienta (PDF corrupto, cifrado, >100 páginas → BadRequestError de
    # Anthropic) NO puede tumbar la sesión entera ni tirar a la basura lo que los demás
    # consejeros ya produjeron: se aísla, se reintenta sin documentos y, si aún así falla,
    # cae a un placeholder que le dice al dueño qué revisar.
    for agent in body.agents:
        agent_types = AGENT_DOC_TYPES.get(agent, set())
        agent_docs, agent_note = select_for_agent(
            [d for d in ready_docs if d["document_type"] in agent_types],
            [d for d in unreadable_board_docs if d["document_type"] in agent_types],
        )
        try:
            revised, critique = await _pipeline(agent, agent_docs, agent_note)
            analyses[agent] = {**revised, "_challenger_applied": True}
            critiques[agent] = critique
            continue
        except Exception:
            _log.exception("pipeline del agente %s falló (con %d documentos)", agent, len(agent_docs))

        if agent_docs:
            # Segundo intento SIN documentos: el dueño al menos obtiene su análisis, aunque
            # el consejero no haya podido leer los papeles.
            try:
                revised, critique = await _pipeline(agent, [], _NOTA_SIN_DOCUMENTOS)
                analyses[agent] = {
                    **revised,
                    "_challenger_applied": True,
                    "_documentos_omitidos": True,
                }
                critiques[agent] = critique
                continue
            except Exception:
                _log.exception("reintento sin documentos del agente %s también falló", agent)

        analyses[agent] = failed_agent_analysis(agent, period_year, period_month)
        critiques[agent] = {}

    # ── La deliberación: cuatro opiniones → UNA conclusión del Consejo ────────────
    # No es un resumen de resúmenes: es la postura del órgano, con sus acuerdos. Si la
    # deliberación falla, la sesión NO se pierde: quedan los análisis de los consejeros.
    conclusion: dict | None = None
    try:
        conclusion = await anyio.to_thread.run_sync(
            lambda: run_deliberacion(
                analyses=analyses,
                critiques=critiques,
                roadmap=roadmap,
                memory_buffer=memory_buffer,
                kpi_snapshot=kpi_snapshot,
                period_year=period_year,
                period_month=period_month,
                documents_note=_NOTA_SIN_DOCUMENTOS if not ready_docs else "",
                avance_tareas=avance_tareas,
                acuerdos_previos=acuerdos_previos,
            )
        )
    except Exception:
        _log.exception("la deliberación del Consejo falló; se conservan los análisis individuales")

    # Abrir una nueva sesión de DB para persistir los resultados
    from app.db.session import AsyncSessionLocal
    from sqlalchemy.orm.attributes import flag_modified
    async with AsyncSessionLocal() as new_db:
        refreshed = await new_db.get(BoardSession, bs_id)
        if refreshed is None:
            raise HTTPException(status_code=404, detail="Sesión no encontrada al persistir.")
        refreshed.agent_analyses = analyses
        refreshed.agent_critiques = critiques
        flag_modified(refreshed, "agent_analyses")
        flag_modified(refreshed, "agent_critiques")

        if conclusion is not None:
            refreshed.conclusion = conclusion
            flag_modified(refreshed, "conclusion")
            # Los acuerdos se materializan como compromisos reales (con responsable, fecha,
            # prioridad y su link de seguimiento). Re-analizar la sesión los reemplaza: los
            # acuerdos son el resultado de ESTA deliberación, no un histórico que se acumula.
            await new_db.execute(
                delete(Compromiso).where(Compromiso.board_session_id == bs_id)
            )
            for a in (conclusion.get("acuerdos") or []):
                try:
                    fecha = date.fromisoformat(a["fecha_sugerida"])
                except (KeyError, TypeError, ValueError):
                    fecha = None
                new_db.add(Compromiso(
                    user_id=user_id,
                    descripcion=a["texto"],
                    responsable_nombre=a.get("responsable_sugerido") or None,
                    responsable_email=None,   # lo pone el dueño: la IA no conoce a su gente
                    fecha_compromiso=fecha,
                    status="abierto",
                    token=secrets.token_urlsafe(16),
                    avances=[],
                    board_session_id=bs_id,
                    prioridad=a.get("prioridad") or "media",
                    pilar=a.get("pilar") or None,
                    racional=a.get("racional") or None,
                    source={"board_session_id": str(bs_id)},
                ))
        await new_db.commit()
        await new_db.refresh(refreshed)
        conclusion_out = await _conclusion_out(new_db, refreshed)

    return {
        "board_session_id": str(bs_id),
        "agents_analysed": body.agents,
        "analyses": normalize_agent_analyses(analyses),
        "conclusion": conclusion_out,
    }


# ── POST /board-sessions/{id}/chat ───────────────────────────────────────────

@router.post("/{board_session_id}/chat", response_model=ChatMessageOut)
async def send_chat_message(
    board_session_id: uuid.UUID,
    body: ChatMessageInput,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Envía un mensaje al agente especificado y devuelve su respuesta."""
    bs = await _get_board_session_or_404(board_session_id, user_id, db)

    target_agent = body.agent or "CFO"
    if target_agent not in VALID_AGENTS:
        raise HTTPException(status_code=400, detail=f"Agente '{target_agent}' no válido.")

    # Guardar mensaje del usuario
    user_msg = ChatMessage(
        board_session_id=board_session_id,
        user_id=user_id,
        role="user",
        agent=None,
        content=body.content,
    )
    db.add(user_msg)
    await db.flush()

    # Obtener perfil base y historial
    onboarding_result = await db.execute(
        select(OnboardingSession).where(OnboardingSession.id == bs.onboarding_session_id)
    )
    onboarding = onboarding_result.scalar_one_or_none()
    memory_buffer = onboarding.memory_buffer if onboarding else {}

    history = [
        {"role": m.role, "content": m.content, "agent": m.agent}
        for m in (bs.messages or [])
        if m.id != user_msg.id
    ]

    # Llamar al agente
    reply_text = run_agent_chat(
        agent=target_agent,
        user_message=body.content,
        memory_buffer=memory_buffer,
        kpi_snapshot=bs.kpi_snapshot,
        chat_history=history,
        period_year=bs.period_year,
        period_month=bs.period_month,
    )

    # Guardar respuesta del agente
    agent_msg = ChatMessage(
        board_session_id=board_session_id,
        user_id=user_id,
        role="assistant",
        agent=target_agent,
        content=reply_text,
    )
    db.add(agent_msg)
    await db.flush()
    await db.commit()

    return ChatMessageOut(
        message_id=str(agent_msg.id),
        role="assistant",
        agent=target_agent,
        content=reply_text,
        created_at=agent_msg.created_at,
    )


# ── POST /board-sessions/{id}/chat/stream ────────────────────────────────────

@router.post("/{board_session_id}/chat/stream")
async def send_chat_message_stream(
    board_session_id: uuid.UUID,
    body: ChatMessageInput,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """
    Igual que /chat pero retorna la respuesta del agente como un stream
    text/plain, para que el frontend pueda mostrarla apareciendo en tiempo real.
    """
    from fastapi.responses import StreamingResponse

    bs = await _get_board_session_or_404(board_session_id, user_id, db)
    target_agent = body.agent or "CFO"
    if target_agent not in VALID_AGENTS:
        raise HTTPException(status_code=400, detail=f"Agente '{target_agent}' no válido.")

    # Guardar mensaje del usuario
    user_msg = ChatMessage(
        board_session_id=board_session_id,
        user_id=user_id,
        role="user",
        agent=None,
        content=body.content,
    )
    db.add(user_msg)
    await db.flush()

    # Capturar historial y contexto ANTES de cerrar la transacción
    onboarding_result = await db.execute(
        select(OnboardingSession).where(OnboardingSession.id == bs.onboarding_session_id)
    )
    onboarding = onboarding_result.scalar_one_or_none()
    memory_buffer = onboarding.memory_buffer if onboarding else {}

    history = [
        {"role": m.role, "content": m.content, "agent": m.agent}
        for m in (bs.messages or [])
        if m.id != user_msg.id
    ]

    # Snapshot de campos a usar dentro del generador
    period_year = bs.period_year
    period_month = bs.period_month
    kpi_snapshot = bs.kpi_snapshot
    bs_id = board_session_id

    # Commit del mensaje del usuario antes de empezar el stream
    await db.commit()

    async def event_generator():
        from app.db.session import AsyncSessionLocal
        accumulated = ""
        try:
            async for chunk in run_agent_chat_stream(
                agent=target_agent,
                user_message=body.content,
                memory_buffer=memory_buffer,
                kpi_snapshot=kpi_snapshot,
                chat_history=history,
                period_year=period_year,
                period_month=period_month,
            ):
                accumulated += chunk
                yield chunk
        finally:
            # Persistir la respuesta del agente cuando termine el stream
            if accumulated:
                async with AsyncSessionLocal() as new_db:
                    agent_msg = ChatMessage(
                        board_session_id=bs_id,
                        user_id=user_id,
                        role="assistant",
                        agent=target_agent,
                        content=accumulated,
                    )
                    new_db.add(agent_msg)
                    await new_db.commit()

    return StreamingResponse(
        event_generator(),
        media_type="text/plain; charset=utf-8",
        headers={"X-Accel-Buffering": "no", "Cache-Control": "no-cache"},
    )


# ── GET /board-sessions/{id}/chat ────────────────────────────────────────────

@router.get("/{board_session_id}/chat", response_model=list[ChatMessageOut])
async def get_chat_history(
    board_session_id: uuid.UUID,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Retorna el historial completo del chat de la sesión."""
    bs = await _get_board_session_or_404(board_session_id, user_id, db)
    return [
        ChatMessageOut(
            message_id=str(m.id),
            role=m.role,
            agent=m.agent,
            content=m.content,
            created_at=m.created_at,
        )
        for m in (bs.messages or [])
    ]
