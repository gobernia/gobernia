import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.dependencies import get_current_user_id, get_db
from app.models.onboarding_session import OnboardingSession
from app.schemas.etapa3 import Etapa3Input, Etapa3Output
from app.services.ai.etapa3_mapping import (
    build_etapa3_memory,
    build_priority_narrative,
    get_lead_agent,
    map_priorities,
)

router = APIRouter()

STAGE_NUMBER = 3


@router.post("/{session_id}/etapa-3", response_model=Etapa3Output)
async def submit_etapa3(
    session_id: uuid.UUID,
    data: Etapa3Input,
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

    completed = list(session.completed_stages or [])
    if 2 not in completed:
        raise HTTPException(status_code=400, detail="Debes completar Etapa 2 antes de continuar")

    mapped = map_priorities(data)
    lead_agent = get_lead_agent(mapped)
    etapa3_data = build_etapa3_memory(mapped, lead_agent)
    narrative = build_priority_narrative(mapped, lead_agent)

    buffer = dict(session.memory_buffer)
    buffer.update(etapa3_data)

    ai_ctx = buffer.get("ai_context", {})
    ai_ctx["company_narrative"] = ai_ctx.get("company_narrative", "") + narrative
    ai_ctx["lead_agent"] = lead_agent.value
    buffer["ai_context"] = ai_ctx

    if STAGE_NUMBER not in completed:
        completed.append(STAGE_NUMBER)

    session.memory_buffer = buffer
    session.completed_stages = completed
    await db.flush()

    return Etapa3Output(
        session_id=str(session_id),
        completed_stages=completed,
        lead_agent=lead_agent,
        priorities_mapped=mapped,
        next_stage=4,
    )
