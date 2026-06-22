import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Response, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified
import anyio

from app.core.dependencies import get_current_user_id, get_db
from app.models.todd_session import ToddSession
from app.models.onboarding_session import OnboardingSession
from app.models.diagnostico_estrategico import DiagnosticoEstrategico
from app.schemas.todd import ToddTurnIn, ToddTurnOut, ToddSessionOut, ToddMessage, ToddEditIn
from app.schemas.todd import ToddMetasOut, ToddMetasIn, FodaOut
from app.services.ai.todd.agent import run_todd_turn, run_todd_edit, state_to_memory_buffer
from app.services.ai.todd.externo import run_externo_turn, run_externo_edit, generar_metas

router = APIRouter()


async def _current(user_id: str, db: AsyncSession, phase: str = "interno") -> ToddSession | None:
    return (await db.execute(
        select(ToddSession).where(ToddSession.user_id == user_id, ToddSession.phase == phase)
        .order_by(ToddSession.created_at.desc())
    )).scalar_one_or_none()


async def _diagnostico_ctx(user_id: str, db: AsyncSession) -> str:
    diag = (await db.execute(
        select(DiagnosticoEstrategico).where(DiagnosticoEstrategico.user_id == user_id)
        .order_by(DiagnosticoEstrategico.created_at.desc())
    )).scalars().first()
    c = (diag.content if diag else {}) or {}
    partes = []
    for s in (c.get("sections") or [])[:3]:
        if s.get("body"):
            partes.append(f"{s.get('title','')}: {s['body'][:600]}")
    fd = c.get("fortalezas_debilidades") or {}
    if fd:
        partes.append("Hallazgos internos: " + json.dumps(fd, ensure_ascii=False)[:1200])
    return "\n".join(partes) or "(sin diagnóstico)"


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
        areas_cubiertas=list((sess.state or {}).get("areas_cubiertas") or []),
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
        areas_cubiertas=list((turn["state"] or {}).get("areas_cubiertas") or []),
    )


@router.post("/onboarding/todd/edit", response_model=ToddTurnOut)
async def todd_edit(
    body: ToddEditIn,
    user_id: str = Depends(get_current_user_id), db: AsyncSession = Depends(get_db),
):
    sess = await _current(user_id, db)
    if sess is None:
        raise HTTPException(status_code=404, detail="No hay entrevista activa.")
    messages = list(sess.messages or [])
    i = body.answer_index
    if i < 0 or i >= len(messages) or messages[i].get("role") != "user":
        raise HTTPException(status_code=400, detail="Índice de respuesta inválido.")

    corrected = [dict(m) for m in messages]
    corrected[i] = {"role": "user", "text": body.nueva_respuesta, "options": None}
    edited_question = messages[i - 1].get("text", "") if i > 0 else ""

    turn = await anyio.to_thread.run_sync(
        lambda: run_todd_edit(corrected, edited_question, body.nueva_respuesta, sess.state or {})
    )

    if turn.get("reanudar_desde") == "rehacer":
        nuevos = corrected[: i + 1] + [{"role": "todd", "text": turn["message"], "options": turn["options"]}]
    else:
        nuevos = corrected + [{"role": "todd", "text": turn["message"], "options": turn["options"]}]

    sess.messages = nuevos
    sess.state = turn["state"] or sess.state
    flag_modified(sess, "messages")
    flag_modified(sess, "state")
    await db.commit()

    return ToddTurnOut(
        message=turn["message"], options=turn["options"],
        input=turn["input"], done=turn["done"],
        areas_cubiertas=list((turn["state"] or {}).get("areas_cubiertas") or []),
    )


@router.get("/onboarding/todd/externo", response_model=ToddSessionOut)
async def get_externo(user_id: str = Depends(get_current_user_id), db: AsyncSession = Depends(get_db)):
    sess = await _current(user_id, db, phase="externo")
    if sess is None:
        return Response(status_code=204)
    return ToddSessionOut(
        status=sess.status, messages=[ToddMessage(**m) for m in (sess.messages or [])],
        done=sess.status == "done",
        areas_cubiertas=list((sess.state or {}).get("areas_cubiertas") or []),
    )


@router.post("/onboarding/todd/externo/turn", response_model=ToddTurnOut)
async def externo_turn(body: ToddTurnIn, user_id: str = Depends(get_current_user_id), db: AsyncSession = Depends(get_db)):
    sess = await _current(user_id, db, phase="externo")
    if sess is None:
        sess = ToddSession(user_id=user_id, status="active", phase="externo", messages=[], state={})
        db.add(sess); await db.flush()
    ctx = await _diagnostico_ctx(user_id, db)
    messages = list(sess.messages or [])
    if body.answer:
        messages.append({"role": "user", "text": body.answer, "options": None})
    turn = await anyio.to_thread.run_sync(lambda: run_externo_turn(messages, sess.state or {}, ctx))
    messages.append({"role": "todd", "text": turn["message"], "options": turn["options"]})
    sess.messages = messages
    sess.state = turn["state"] or sess.state
    if turn["done"]:
        sess.status = "done"
    flag_modified(sess, "messages"); flag_modified(sess, "state")
    await db.commit()
    return ToddTurnOut(message=turn["message"], options=turn["options"], input=turn["input"],
                       done=turn["done"], areas_cubiertas=list((turn["state"] or {}).get("areas_cubiertas") or []))


@router.post("/onboarding/todd/externo/edit", response_model=ToddTurnOut)
async def externo_edit(body: ToddEditIn, user_id: str = Depends(get_current_user_id), db: AsyncSession = Depends(get_db)):
    sess = await _current(user_id, db, phase="externo")
    if sess is None:
        raise HTTPException(status_code=404, detail="No hay ronda externa activa.")
    messages = list(sess.messages or [])
    i = body.answer_index
    if i < 0 or i >= len(messages) or messages[i].get("role") != "user":
        raise HTTPException(status_code=400, detail="Índice de respuesta inválido.")
    ctx = await _diagnostico_ctx(user_id, db)
    corrected = [dict(m) for m in messages]
    corrected[i] = {"role": "user", "text": body.nueva_respuesta, "options": None}
    edited_question = messages[i - 1].get("text", "") if i > 0 else ""
    turn = await anyio.to_thread.run_sync(
        lambda: run_externo_edit(corrected, edited_question, body.nueva_respuesta, sess.state or {}, ctx))
    if turn.get("reanudar_desde") == "rehacer":
        nuevos = corrected[: i + 1] + [{"role": "todd", "text": turn["message"], "options": turn["options"]}]
    else:
        nuevos = corrected + [{"role": "todd", "text": turn["message"], "options": turn["options"]}]
    sess.messages = nuevos
    sess.state = turn["state"] or sess.state
    flag_modified(sess, "messages"); flag_modified(sess, "state")
    await db.commit()
    return ToddTurnOut(message=turn["message"], options=turn["options"], input=turn["input"],
                       done=turn["done"], areas_cubiertas=list((turn["state"] or {}).get("areas_cubiertas") or []))


@router.get("/onboarding/todd/metas", response_model=ToddMetasOut)
async def get_metas(user_id: str = Depends(get_current_user_id), db: AsyncSession = Depends(get_db)):
    interno = await _current(user_id, db, phase="interno")
    externo = await _current(user_id, db, phase="externo")
    ctx = await _diagnostico_ctx(user_id, db)
    metas = await anyio.to_thread.run_sync(lambda: generar_metas(
        ctx, (interno.state if interno else {}) or {}, (externo.state if externo else {}) or {}))
    return ToddMetasOut(metas=metas)


@router.post("/onboarding/todd/metas")
async def save_metas(body: ToddMetasIn, user_id: str = Depends(get_current_user_id), db: AsyncSession = Depends(get_db)):
    diag = (await db.execute(
        select(DiagnosticoEstrategico).where(DiagnosticoEstrategico.user_id == user_id)
        .order_by(DiagnosticoEstrategico.created_at.desc())
    )).scalars().first()
    if diag is None:
        raise HTTPException(status_code=404, detail="No hay diagnóstico.")
    externo = await _current(user_id, db, phase="externo")
    content = dict(diag.content or {})
    content["factores_externos"] = ((externo.state if externo else {}) or {}).get("factores_externos") or {}
    content["metas_orden"] = [str(m) for m in body.orden]
    content["foda_status"] = "generating"
    diag.content = content
    flag_modified(diag, "content")
    await db.commit()
    try:
        from app.tasks.foda_tasks import generate_foda_task
        generate_foda_task.delay(user_id)
    except Exception:
        content["foda_status"] = "failed"
        diag.content = content
        flag_modified(diag, "content")
        await db.commit()
    return {"ok": True}


@router.get("/onboarding/foda", response_model=FodaOut)
async def get_foda(user_id: str = Depends(get_current_user_id), db: AsyncSession = Depends(get_db)):
    diag = (await db.execute(
        select(DiagnosticoEstrategico).where(DiagnosticoEstrategico.user_id == user_id)
        .order_by(DiagnosticoEstrategico.created_at.desc())
    )).scalars().first()
    if diag is None:
        raise HTTPException(status_code=404, detail="No hay análisis.")
    c = diag.content or {}
    return FodaOut(status=c.get("foda_status") or "none", foda=c.get("foda"),
                   metas=c.get("metas_orden") or [])


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
