"""Task de Celery de consolidación de perspectivas (espejo de foda_tasks). Sin web."""
import asyncio

from sqlalchemy import select
from sqlalchemy.orm.attributes import flag_modified

from app.tasks.worker import celery_app
from app.models.diagnostico_estrategico import DiagnosticoEstrategico
from app.models.onboarding_session import OnboardingSession
from app.models.perspectiva_invite import PerspectivaInvite
from app.services.ai.perspectivas.consolidar import consolidar_perspectivas


@celery_app.task(name="generate_perspectivas", bind=True, max_retries=1)
def generate_perspectivas_task(self, user_id: str) -> dict:
    try:
        return asyncio.run(_run(user_id))
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
        mb = (onb.memory_buffer if onb else {}) or {}
        rows = (await db.execute(
            select(PerspectivaInvite).where(
                PerspectivaInvite.owner_user_id == user_id, PerspectivaInvite.status == "done")
        )).scalars().all()
        invites = [{"role": r.role, "name": r.invitee_name, "state": r.state or {},
                    "messages": r.messages or []} for r in rows]
        content = dict(diag.content or {})
        try:
            sintesis = await asyncio.to_thread(consolidar_perspectivas, mb, invites)
            sintesis["status"] = "active"
            content["perspectivas"] = sintesis
        except Exception:
            content["perspectivas"] = {"status": "failed"}
        diag.content = content
        flag_modified(diag, "content")
        await db.commit()
    return {"status": "active", "user_id": user_id}
