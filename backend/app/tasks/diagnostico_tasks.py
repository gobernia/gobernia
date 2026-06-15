"""Task de Celery del Diagnóstico estratégico (espejo de annual_plan_tasks)."""
import asyncio

from sqlalchemy import select

from app.tasks.worker import celery_app
from app.models.diagnostico_estrategico import DiagnosticoEstrategico
from app.models.onboarding_session import OnboardingSession
from app.services.ai.diagnostico_estrategico import generate_diagnostico


@celery_app.task(name="generate_diagnostico", bind=True, max_retries=2)
def generate_diagnostico_task(self, diagnostico_id: str) -> dict:
    try:
        return asyncio.run(_entrypoint(diagnostico_id))
    except Exception as exc:
        raise self.retry(exc=exc, countdown=30)


async def _entrypoint(diagnostico_id: str) -> dict:
    from app.db.session import task_session
    async with task_session() as db:
        await _run_generation(diagnostico_id, db)
    return {"status": "active", "diagnostico_id": diagnostico_id}


async def _run_generation(diagnostico_id: str, db) -> None:
    diag = (await db.execute(
        select(DiagnosticoEstrategico).where(DiagnosticoEstrategico.id == diagnostico_id)
    )).scalar_one_or_none()
    if diag is None:
        return

    try:
        onboarding = (await db.execute(
            select(OnboardingSession).where(OnboardingSession.user_id == diag.user_id)
            .order_by(OnboardingSession.created_at.desc())
        )).scalars().first()
        memory_buffer = (onboarding.memory_buffer if onboarding else {}) or {}

        content = await asyncio.to_thread(generate_diagnostico, memory_buffer)

        diag.content = content
        diag.status = "active"
        await db.commit()
    except Exception:
        await db.rollback()
        diag = (await db.execute(
            select(DiagnosticoEstrategico).where(DiagnosticoEstrategico.id == diagnostico_id)
        )).scalar_one_or_none()
        if diag is not None:
            diag.status = "failed"
            diag.fail_reason = "error"
            await db.commit()
        raise
