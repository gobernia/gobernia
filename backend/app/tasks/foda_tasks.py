"""Task de Celery del FODA (espejo de diagnostico_tasks). Sin web, rápida."""
import asyncio

from celery.exceptions import SoftTimeLimitExceeded
from sqlalchemy import select
from sqlalchemy.orm.attributes import flag_modified

from app.tasks.worker import celery_app
from app.models.diagnostico_estrategico import DiagnosticoEstrategico
from app.models.onboarding_session import OnboardingSession
from app.services.ai.foda import generate_foda


@celery_app.task(name="generate_foda", bind=True, max_retries=1)
def generate_foda_task(self, user_id: str) -> dict:
    try:
        return asyncio.run(_run(user_id))
    except SoftTimeLimitExceeded:
        raise
    except Exception as exc:
        raise self.retry(exc=exc, countdown=20)


async def _run(user_id: str) -> dict:
    from app.db.session import task_session
    async with task_session() as db:
        diag = (await db.execute(
            select(DiagnosticoEstrategico).where(DiagnosticoEstrategico.user_id == user_id)
            .order_by(DiagnosticoEstrategico.created_at.desc())
        )).scalars().first()
        if diag is None:
            return {"status": "skipped"}
        onb = (await db.execute(
            select(OnboardingSession).where(OnboardingSession.user_id == user_id)
            .order_by(OnboardingSession.created_at.desc())
        )).scalars().first()
        memory_buffer = (onb.memory_buffer if onb else {}) or {}
        content = dict(diag.content or {})
        try:
            foda = await asyncio.to_thread(
                generate_foda, memory_buffer, content,
                content.get("factores_externos") or {}, content.get("metas_orden") or [],
                content.get("perspectivas") or {})
            content["foda"] = foda
            content["foda_status"] = "active"
        except Exception:
            content["foda_status"] = "failed"
        diag.content = content
        flag_modified(diag, "content")
        await db.commit()
    return {"status": "active", "user_id": user_id}
