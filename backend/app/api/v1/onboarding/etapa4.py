import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.dependencies import get_current_user_id, get_db
from app.models.onboarding_session import OnboardingSession
from app.schemas.etapa4 import Etapa4Input, Etapa4Output, Etapa4QuestionsOutput
from app.services.ai.question_engine import build_question_set
from app.services.ai.matrix_engine import build_etapa4_memory, generate_matrices

router = APIRouter()

STAGE_NUMBER = 4


@router.get("/{session_id}/etapa-4/questions", response_model=Etapa4QuestionsOutput)
async def get_etapa4_questions(
    session_id: uuid.UUID,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Retorna el set personalizado de preguntas para esta empresa."""
    result = await db.execute(
        select(OnboardingSession).where(
            OnboardingSession.id == session_id,
            OnboardingSession.user_id == user_id,
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Sesión no encontrada")
    if 3 not in (session.completed_stages or []):
        raise HTTPException(status_code=400, detail="Debes completar Etapa 3 antes de continuar")

    questions = build_question_set(session.memory_buffer)
    return Etapa4QuestionsOutput(
        session_id=str(session_id),
        questions=questions,
        total_questions=len(questions),
    )


@router.post("/{session_id}/etapa-4", response_model=Etapa4Output)
async def submit_etapa4(
    session_id: uuid.UUID,
    data: Etapa4Input,
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
    if 3 not in completed:
        raise HTTPException(status_code=400, detail="Debes completar Etapa 3 antes de continuar")

    buffer = dict(session.memory_buffer)
    questions = build_question_set(buffer)
    matrices = generate_matrices(questions, data.responses, buffer)
    etapa4_data = build_etapa4_memory(questions, data.responses, matrices)

    buffer.update(etapa4_data)
    ai_ctx = buffer.get("ai_context", {})
    ai_ctx["company_narrative"] = (
        ai_ctx.get("company_narrative", "") +
        f" Diagnóstico: {matrices.business_summary}"
    )
    buffer["ai_context"] = ai_ctx

    if STAGE_NUMBER not in completed:
        completed.append(STAGE_NUMBER)

    session.memory_buffer = buffer
    session.completed_stages = completed
    await db.flush()

    return Etapa4Output(
        session_id=str(session_id),
        completed_stages=completed,
        matrices=matrices,
        next_stage=5,
    )
