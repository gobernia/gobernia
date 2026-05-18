"""
Router de onboarding.
Cada etapa tendrá su propio endpoint POST que:
1. Valida los datos de entrada con Pydantic
2. Actualiza el Memory Buffer en la DB
3. Ejecuta inferencias de IA si aplica
4. Marca la etapa como completada
5. Retorna el Memory Buffer actualizado
"""
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.dependencies import get_current_user_id, get_db
from app.models.onboarding_session import OnboardingSession
from app.schemas.memory_buffer import GoberniaMemoryBuffer
from app.api.v1.onboarding.etapa1 import router as etapa1_router
from app.api.v1.onboarding.etapa2 import router as etapa2_router
from app.api.v1.onboarding.etapa3 import router as etapa3_router
from app.api.v1.onboarding.etapa4 import router as etapa4_router
from app.api.v1.onboarding.etapa5 import router as etapa5_router
from app.api.v1.onboarding.etapa6 import router as etapa6_router
from app.api.v1.onboarding.etapa7 import router as etapa7_router
from app.api.v1.onboarding.etapa8 import router as etapa8_router

router = APIRouter()
router.include_router(etapa1_router)
router.include_router(etapa2_router)
router.include_router(etapa3_router)
router.include_router(etapa4_router)
router.include_router(etapa5_router)
router.include_router(etapa6_router)
router.include_router(etapa7_router)
router.include_router(etapa8_router)


@router.post("/session", status_code=status.HTTP_201_CREATED)
async def create_session(
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Crea una nueva sesión de onboarding para el usuario."""
    session = OnboardingSession(
        user_id=user_id,
        completed_stages=[],
        memory_buffer={
            "session_id": str(uuid.uuid4()),
            "user_id": user_id,
            "completed_stages": [],
            "team": [],
            "priorities": [],
            "diagnostic_responses": [],
            "documents": [],
            "onboarding_started_at": datetime.now(timezone.utc).isoformat(),
        },
    )
    db.add(session)
    await db.flush()
    return {"session_id": str(session.id), "status": "created"}


@router.get("/session/{session_id}")
async def get_session(
    session_id: uuid.UUID,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Retorna el estado actual del Memory Buffer para una sesión."""
    result = await db.execute(
        select(OnboardingSession).where(
            OnboardingSession.id == session_id,
            OnboardingSession.user_id == user_id,
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Sesión no encontrada")
    return {
        "session_id": str(session.id),
        "completed_stages": session.completed_stages,
        "memory_buffer": session.memory_buffer,
        "governance_score": session.governance_score,
        "completed_at": session.completed_at,
    }


@router.get("/my-session")
async def get_my_session(
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """
    Retorna la sesión de onboarding más reciente del usuario, o 204 si no hay.
    Usado por el dashboard para hidratar el store cuando el usuario entra
    desde un dispositivo / navegador nuevo.
    """
    result = await db.execute(
        select(OnboardingSession)
        .where(OnboardingSession.user_id == user_id)
        .order_by(OnboardingSession.created_at.desc())
        .limit(1)
    )
    session = result.scalar_one_or_none()
    if not session:
        from fastapi import Response
        return Response(status_code=204)
    return {
        "session_id": str(session.id),
        "completed_stages": session.completed_stages or [],
        "governance_score": session.governance_score,
        "completed_at": session.completed_at,
    }


@router.get("/{session_id}/summary")
async def get_session_summary(
    session_id: uuid.UUID,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Retorna el resumen de la sesión para el dashboard."""
    result = await db.execute(
        select(OnboardingSession).where(
            OnboardingSession.id == session_id,
            OnboardingSession.user_id == user_id,
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Sesión no encontrada")

    buf = session.memory_buffer or {}
    company = buf.get("company", {})
    return {
        "company_name": company.get("name"),
        "industry": company.get("industry"),
        "governance_score": session.governance_score,
        "activated_modules": buf.get("activated_modules", []),
        "completed_stages": session.completed_stages or [],
        "diagnostic_area_completion": buf.get("diagnostic_area_completion", {}),
    }


@router.get("/session/{session_id}/progress")
async def get_progress(
    session_id: uuid.UUID,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Retorna el progreso de las etapas completadas."""
    result = await db.execute(
        select(OnboardingSession).where(
            OnboardingSession.id == session_id,
            OnboardingSession.user_id == user_id,
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Sesión no encontrada")

    total_stages = 8
    completed = session.completed_stages or []
    return {
        "completed_stages": completed,
        "total_stages": total_stages,
        "percentage": round(len(completed) / total_stages * 100),
        "next_stage": min([s for s in range(1, 9) if s not in completed], default=None),
        "is_complete": len(completed) == total_stages,
    }
