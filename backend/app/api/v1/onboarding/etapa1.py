import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.dependencies import get_current_user_id, get_db
from app.models.onboarding_session import OnboardingSession
from app.schemas.etapa1 import Etapa1Input, Etapa1Output
from app.services.ai.memory_buffer import (
    build_company_narrative,
    build_etapa1_memory,
    evaluate_etapa1_modules,
)

router = APIRouter()

STAGE_NUMBER = 1


@router.post("/{session_id}/etapa-1", response_model=Etapa1Output)
async def submit_etapa1(
    session_id: uuid.UUID,
    data: Etapa1Input,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(OnboardingSession).where(
            OnboardingSession.id == session_id,
            OnboardingSession.user_id == user_id,
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Sesión no encontrada")

    # Evaluar condicionales del spec
    activated_modules = evaluate_etapa1_modules(data)

    # Construir fragmento del Memory Buffer
    etapa1_data = build_etapa1_memory(data, activated_modules)
    narrative = build_company_narrative(data, activated_modules)

    # Fusionar con el buffer existente
    buffer = dict(session.memory_buffer)
    buffer.update(etapa1_data)
    buffer["ai_context"] = buffer.get("ai_context", {})
    buffer["ai_context"]["company_narrative"] = narrative
    buffer["ai_context"]["activated_modules"] = activated_modules

    # Marcar etapa como completada
    completed = list(session.completed_stages or [])
    if STAGE_NUMBER not in completed:
        completed.append(STAGE_NUMBER)

    session.memory_buffer = buffer
    session.completed_stages = completed
    await db.flush()

    return Etapa1Output(
        session_id=str(session_id),
        completed_stages=completed,
        activated_modules=activated_modules,
        next_stage=2,
        summary=narrative,
    )
