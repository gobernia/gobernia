"""
Etapa 8 — Visión, Expectativas y Configuración de Agentes
GET  /{session_id}/etapa-8/options  → opciones de tono, sensibilidad y frecuencia
POST /{session_id}/etapa-8          → guarda visión + config agentes en Memory Buffer
"""
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from sqlalchemy.orm.attributes import flag_modified

from app.core.dependencies import get_current_user_id, get_db
from app.models.onboarding_session import OnboardingSession
from app.schemas.etapa8 import (
    VALID_AGENTS,
    VALID_FREQUENCIES,
    VALID_SENSITIVITIES,
    VALID_TONES,
    Etapa8ConfigOptions,
    Etapa8Input,
    Etapa8Output,
)
from app.services.ai.etapa8_builder import (
    build_agent_summaries,
    build_etapa8_memory,
    update_ai_context_with_vision,
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


@router.get("/{session_id}/etapa-8/options", response_model=Etapa8ConfigOptions)
async def get_config_options(
    session_id: uuid.UUID,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Retorna las opciones disponibles para configurar agentes y expectativas."""
    session = await _get_session_or_404(session_id, user_id, db)

    if 7 not in (session.completed_stages or []):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Debes completar la Etapa 7 antes de continuar.",
        )

    return Etapa8ConfigOptions(
        agents=sorted(VALID_AGENTS),
        tones=VALID_TONES,
        sensitivities=VALID_SENSITIVITIES,
        frequencies=VALID_FREQUENCIES,
    )


@router.post("/{session_id}/etapa-8", response_model=Etapa8Output)
async def submit_etapa8(
    session_id: uuid.UUID,
    body: Etapa8Input,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Guarda la visión, expectativas del consejo y configuración de los 4 agentes."""
    session = await _get_session_or_404(session_id, user_id, db)

    if 7 not in (session.completed_stages or []):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Debes completar la Etapa 7 antes de continuar.",
        )

    buf = dict(session.memory_buffer or {})

    # Actualizar ai_context.company_narrative con la visión
    ai_ctx = dict(buf.get("ai_context", {}))
    ai_ctx["company_narrative"] = update_ai_context_with_vision(buf, body)
    buf["ai_context"] = ai_ctx

    # Guardar bloque de visión y configs de agentes
    buf.update(build_etapa8_memory(body))
    session.memory_buffer = buf
    flag_modified(session, "memory_buffer")

    completed = list(session.completed_stages or [])
    if 8 not in completed:
        completed.append(8)
    session.completed_stages = completed

    await db.flush()
    await db.commit()

    # Disparar generación del plan de 12 meses (solo la primera vez que se cierra el onboarding).
    if 8 in completed:
        from app.models.annual_plan import AnnualPlan
        from datetime import date as _date
        existing = await db.execute(
            select(AnnualPlan).where(AnnualPlan.user_id == user_id).limit(1)
        )
        if existing.scalar_one_or_none() is None:
            plan = AnnualPlan(
                user_id=user_id, title="Plan estratégico de 12 meses",
                start_date=_date.today(), status="generating",
            )
            db.add(plan)
            await db.flush()
            await db.commit()
            from app.tasks.annual_plan_tasks import generate_annual_plan_task
            generate_annual_plan_task.delay(str(plan.id))

    return Etapa8Output(
        session_id=str(session.id),
        completed_stages=completed,
        vision_statement=body.vision_statement,
        main_goals=body.main_goals,
        agent_configs=build_agent_summaries(body.agent_configs),
        session_frequency=body.board_expectations.session_frequency,
        next_stage=9,
    )
