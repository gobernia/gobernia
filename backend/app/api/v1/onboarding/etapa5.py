"""
Etapa 5 — Números Clave (KPIs)
GET  /{session_id}/etapa-5/kpis   → templates filtrados por industria/tamaño
POST /{session_id}/etapa-5        → valores ingresados, alertas, Memory Buffer
"""
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.dependencies import get_current_user_id, get_db
from app.models.onboarding_session import OnboardingSession
from app.schemas.etapa5 import Etapa5Input, Etapa5KPIsOutput, Etapa5Output
from app.services.ai.kpi_engine import (
    build_etapa5_memory,
    build_kpi_templates,
    process_kpi_values,
    _get_headcount_from_buffer,
)

router = APIRouter()


async def _get_session_or_404(
    session_id: uuid.UUID,
    user_id: str,
    db: AsyncSession,
) -> OnboardingSession:
    result = await db.execute(
        select(OnboardingSession).where(
            OnboardingSession.id == session_id,
            OnboardingSession.user_id == user_id,
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Sesión no encontrada")
    return session


@router.get("/{session_id}/etapa-5/kpis", response_model=Etapa5KPIsOutput)
async def get_kpi_templates(
    session_id: uuid.UUID,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Retorna los KPI templates filtrados con benchmarks pre-llenados."""
    session = await _get_session_or_404(session_id, user_id, db)

    if 4 not in (session.completed_stages or []):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Debes completar la Etapa 4 antes de continuar.",
        )

    buf = session.memory_buffer or {}
    templates = build_kpi_templates(buf)
    headcount = _get_headcount_from_buffer(buf)

    return Etapa5KPIsOutput(
        session_id=str(session.id),
        kpi_templates=templates,
        total_kpis=len(templates),
        headcount_auto=headcount,
    )


@router.post("/{session_id}/etapa-5", response_model=Etapa5Output)
async def submit_etapa5(
    session_id: uuid.UUID,
    body: Etapa5Input,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Recibe valores KPI, corre alertas y guarda en Memory Buffer."""
    session = await _get_session_or_404(session_id, user_id, db)

    if 4 not in (session.completed_stages or []):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Debes completar la Etapa 4 antes de continuar.",
        )

    buf = session.memory_buffer or {}
    templates = build_kpi_templates(buf)
    results, alerts = process_kpi_values(templates, body.kpis, buf)

    # Actualizar Memory Buffer
    new_buf = dict(buf)
    new_buf.update(build_etapa5_memory(results, alerts))
    session.memory_buffer = new_buf

    completed = list(session.completed_stages or [])
    if 5 not in completed:
        completed.append(5)
    session.completed_stages = completed

    await db.flush()
    await db.commit()

    return Etapa5Output(
        session_id=str(session.id),
        completed_stages=completed,
        kpi_results=results,
        alerts=alerts,
        gap_count=sum(1 for r in results if r.is_gap),
        next_stage=6,
    )
