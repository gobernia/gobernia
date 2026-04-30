"""
Etapa 6 — Gobierno y Cumplimiento
GET  /{session_id}/etapa-6/items  → checklist de gobierno filtrado
POST /{session_id}/etapa-6        → calcula Governance Score, actualiza Memory Buffer
"""
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.dependencies import get_current_user_id, get_db
from app.models.onboarding_session import OnboardingSession
from app.schemas.etapa6 import Etapa6Input, Etapa6ItemsOutput, Etapa6Output
from app.services.ai.governance_engine import (
    build_etapa6_memory,
    build_governance_items,
    calculate_governance_score,
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


@router.get("/{session_id}/etapa-6/items", response_model=Etapa6ItemsOutput)
async def get_governance_items(
    session_id: uuid.UUID,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Retorna el checklist de gobierno filtrado (con/sin ítems familiares)."""
    session = await _get_session_or_404(session_id, user_id, db)

    if 5 not in (session.completed_stages or []):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Debes completar la Etapa 5 antes de continuar.",
        )

    buf = session.memory_buffer or {}
    items = build_governance_items(buf)
    is_family = buf.get("company", {}).get("is_family_business", False)

    return Etapa6ItemsOutput(
        session_id=str(session.id),
        items=items,
        total_items=len(items),
        includes_family=bool(is_family),
    )


@router.post("/{session_id}/etapa-6", response_model=Etapa6Output)
async def submit_etapa6(
    session_id: uuid.UUID,
    body: Etapa6Input,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Calcula el Governance Score y guarda en Memory Buffer y columna governance_score."""
    session = await _get_session_or_404(session_id, user_id, db)

    if 5 not in (session.completed_stages or []):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Debes completar la Etapa 5 antes de continuar.",
        )

    buf = session.memory_buffer or {}
    items = build_governance_items(buf)
    score, level, dim_scores, gaps, recommendations = calculate_governance_score(items, body.items)

    # Actualizar Memory Buffer
    new_buf = dict(buf)
    new_buf.update(build_etapa6_memory(score, level, dim_scores, gaps))
    session.memory_buffer = new_buf

    # Guardar en columna dedicada del modelo (visible en dashboard)
    session.governance_score = score

    completed = list(session.completed_stages or [])
    if 6 not in completed:
        completed.append(6)
    session.completed_stages = completed

    await db.flush()
    await db.commit()

    return Etapa6Output(
        session_id=str(session.id),
        completed_stages=completed,
        governance_score=score,
        governance_level=level,
        dimension_scores=dim_scores,
        gaps=gaps,
        recommendations=recommendations,
        next_stage=7,
    )
