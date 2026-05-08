import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from sqlalchemy.orm.attributes import flag_modified

from app.core.dependencies import get_current_user_id, get_db
from app.models.onboarding_session import OnboardingSession
from app.schemas.etapa2 import Etapa2Input, Etapa2Output
from app.services.ai.etapa2_inferences import build_etapa2_memory, run_etapa2_inferences

router = APIRouter()

STAGE_NUMBER = 2


@router.post("/{session_id}/etapa-2", response_model=Etapa2Output)
async def submit_etapa2(
    session_id: uuid.UUID,
    data: Etapa2Input,
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

    if 1 not in (session.completed_stages or []):
        raise HTTPException(status_code=400, detail="Debes completar Etapa 1 antes de continuar")

    buffer = dict(session.memory_buffer)
    is_family_business = buffer.get("company", {}).get("is_family_business", False)

    inferences = run_etapa2_inferences(data, is_family_business)
    etapa2_data = build_etapa2_memory(data, inferences)

    buffer.update(etapa2_data)

    # Actualizar narrativa con info del equipo
    team_summary = f" Equipo directivo: {len(data.team)} personas."
    if inferences.continuity_risk:
        team_summary += " Alta centralización detectada."
    if inferences.functional_gaps:
        gap_names = ", ".join(g.value for g in inferences.functional_gaps)
        team_summary += f" Gaps funcionales: {gap_names}."

    ai_ctx = buffer.get("ai_context", {})
    ai_ctx["company_narrative"] = ai_ctx.get("company_narrative", "") + team_summary
    buffer["ai_context"] = ai_ctx

    completed = list(session.completed_stages or [])
    if STAGE_NUMBER not in completed:
        completed.append(STAGE_NUMBER)

    session.memory_buffer = buffer
    flag_modified(session, "memory_buffer")
    session.completed_stages = completed
    await db.flush()

    return Etapa2Output(
        session_id=str(session_id),
        completed_stages=completed,
        team_count=len(data.team),
        inferences=inferences,
        next_stage=3,
    )
