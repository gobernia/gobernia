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
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.dependencies import get_current_user_id, get_db
from app.models.board_session import BoardSession
from app.models.chat_message import ChatMessage
from app.models.onboarding_session import OnboardingSession
from app.schemas.board_session import (
    AnalysisRequest,
    BoardSessionCreate,
    BoardSessionDetail,
    BoardSessionKPIsInput,
    BoardSessionSummary,
    ChatMessageInput,
    ChatMessageOut,
)
from app.services.ai.agents.base import (
    run_agent_analysis,
    run_agent_chat,
    run_agent_chat_stream,
    run_challenger_critique,
    run_agent_revision,
)

router = APIRouter(prefix="/board-sessions", tags=["board-sessions"])

_MONTH_NAMES = [
    "", "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
    "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre",
]
VALID_AGENTS = {"CFO", "CSO", "CRO", "Auditor"}


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
        agent_analyses=bs.agent_analyses,
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

    # Ejecutar pipeline por agente: análisis inicial → crítica del Challenger → revisión
    analyses = dict(bs.agent_analyses or {})
    critiques = dict(bs.agent_critiques or {})
    for agent in body.agents:
        initial = run_agent_analysis(
            agent=agent,
            memory_buffer=memory_buffer,
            kpi_snapshot=bs.kpi_snapshot,
            period_year=bs.period_year,
            period_month=bs.period_month,
            previous_analyses=previous_analyses,
        )
        critique = run_challenger_critique(
            agent=agent,
            initial_analysis=initial,
            memory_buffer=memory_buffer,
            kpi_snapshot=bs.kpi_snapshot,
            period_year=bs.period_year,
            period_month=bs.period_month,
        )
        revised = run_agent_revision(
            agent=agent,
            initial_analysis=initial,
            critique=critique,
            memory_buffer=memory_buffer,
            kpi_snapshot=bs.kpi_snapshot,
            period_year=bs.period_year,
            period_month=bs.period_month,
            previous_analyses=previous_analyses,
        )
        analyses[agent] = {**revised, "_challenger_applied": True}
        critiques[agent] = critique

    bs.agent_analyses = analyses
    bs.agent_critiques = critiques
    await db.flush()
    await db.commit()

    return {
        "board_session_id": str(bs.id),
        "agents_analysed": body.agents,
        "analyses": analyses,
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
