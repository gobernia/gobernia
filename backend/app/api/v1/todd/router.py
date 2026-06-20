from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified
import anyio

from app.core.dependencies import get_current_user_id, get_db
from app.models.todd_session import ToddSession
from app.models.onboarding_session import OnboardingSession
from app.models.diagnostico_estrategico import DiagnosticoEstrategico
from app.schemas.todd import ToddTurnIn, ToddTurnOut, ToddSessionOut, ToddMessage
from app.services.ai.todd.agent import run_todd_turn, state_to_memory_buffer

router = APIRouter()


async def _current(user_id: str, db: AsyncSession) -> ToddSession | None:
    return (await db.execute(
        select(ToddSession).where(ToddSession.user_id == user_id)
        .order_by(ToddSession.created_at.desc())
    )).scalar_one_or_none()


@router.get("/onboarding/todd", response_model=ToddSessionOut)
async def get_todd(
    user_id: str = Depends(get_current_user_id), db: AsyncSession = Depends(get_db),
):
    sess = await _current(user_id, db)
    if sess is None:
        return Response(status_code=204)
    return ToddSessionOut(
        status=sess.status,
        messages=[ToddMessage(**m) for m in (sess.messages or [])],
        done=sess.status == "done",
    )


@router.post("/onboarding/todd/turn", response_model=ToddTurnOut)
async def todd_turn(
    body: ToddTurnIn,
    user_id: str = Depends(get_current_user_id), db: AsyncSession = Depends(get_db),
):
    sess = await _current(user_id, db)
    if sess is None:
        sess = ToddSession(user_id=user_id, status="active", messages=[], state={})
        db.add(sess)
        await db.flush()

    messages = list(sess.messages or [])
    if body.answer:
        messages.append({"role": "user", "text": body.answer, "options": None})

    turn = await anyio.to_thread.run_sync(lambda: run_todd_turn(messages, sess.state or {}))

    messages.append({"role": "todd", "text": turn["message"], "options": turn["options"]})
    sess.messages = messages
    sess.state = turn["state"] or sess.state
    flag_modified(sess, "messages")
    flag_modified(sess, "state")
    await db.commit()

    return ToddTurnOut(
        message=turn["message"], options=turn["options"],
        input=turn["input"], done=turn["done"],
    )


@router.post("/onboarding/todd/close")
async def todd_close(
    user_id: str = Depends(get_current_user_id), db: AsyncSession = Depends(get_db),
):
    sess = await _current(user_id, db)
    if sess is None:
        return {"ok": False}
    sess.status = "done"

    onb = (await db.execute(
        select(OnboardingSession).where(OnboardingSession.user_id == user_id)
        .order_by(OnboardingSession.created_at.desc())
    )).scalars().first()
    if onb is None:
        onb = OnboardingSession(user_id=user_id, completed_stages=[], memory_buffer={})
        db.add(onb)

    onb.memory_buffer = state_to_memory_buffer(sess.state or {})
    onb.completed_stages = [1, 2, 3, 4, 5, 6, 7, 8]
    onb.completed_at = datetime.now(timezone.utc)
    flag_modified(onb, "memory_buffer")
    flag_modified(onb, "completed_stages")
    await db.commit()

    # Disparar el diagnóstico combinado (interno + web). Reemplaza el diagnóstico previo si lo hubiera.
    prev = (await db.execute(
        select(DiagnosticoEstrategico).where(DiagnosticoEstrategico.user_id == user_id)
        .order_by(DiagnosticoEstrategico.created_at.desc())
    )).scalars().first()
    if prev is not None:
        await db.delete(prev)
        await db.flush()
    diag = DiagnosticoEstrategico(user_id=user_id, status="generating")
    db.add(diag)
    await db.flush()
    await db.commit()
    try:
        from app.tasks.diagnostico_tasks import generate_diagnostico_task
        generate_diagnostico_task.delay(str(diag.id))
    except Exception:
        diag.status = "failed"
        diag.fail_reason = "no se pudo encolar"
        await db.commit()
    return {"ok": True}
