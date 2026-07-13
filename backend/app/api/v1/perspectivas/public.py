import anyio
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.api.v1.company.service import get_logo_data_url
from app.core.dependencies import get_db
from app.models.perspectiva_invite import PerspectivaInvite
from app.services.ai.perspectivas.agent import run_perspectiva_turn
from app.api.v1.perspectivas.router import _empresa_ctx_for

router = APIRouter()


class PublicAnswerIn(BaseModel):
    answer: str | None = None


async def _get_invite_or_404(token: str, db: AsyncSession) -> PerspectivaInvite:
    inv = (await db.execute(
        select(PerspectivaInvite).where(PerspectivaInvite.token == token)
    )).scalar_one_or_none()
    if inv is None:
        raise HTTPException(status_code=404, detail="Invitación no encontrada o expirada.")
    return inv


@router.get("/perspectiva/{token}")
async def get_perspectiva(token: str, db: AsyncSession = Depends(get_db)):
    inv = await _get_invite_or_404(token, db)
    company_name = await _empresa_ctx_for(inv.owner_user_id, db)
    # Logo del dueño de la invitación (data URL) para marcar la página pública. None si no hay.
    try:
        logo = await get_logo_data_url(inv.owner_user_id, db)
    except Exception:
        logo = None
    return {
        "role": inv.role,
        "company_name": company_name,
        "logo": logo,
        "messages": inv.messages or [],
        "done": inv.status == "done",
    }


@router.post("/perspectiva/{token}/turn")
async def turn_perspectiva(token: str, body: PublicAnswerIn, db: AsyncSession = Depends(get_db)):
    inv = await _get_invite_or_404(token, db)
    if inv.status == "done":
        raise HTTPException(status_code=409, detail="Esta entrevista ya terminó. ¡Gracias!")
    company_ctx = await _empresa_ctx_for(inv.owner_user_id, db)
    messages = list(inv.messages or [])
    if body.answer:
        messages.append({"role": "user", "text": body.answer, "options": None})
    turn = await anyio.to_thread.run_sync(
        lambda: run_perspectiva_turn(messages, inv.state or {}, inv.role, company_ctx))
    messages.append({"role": "todd", "text": turn["message"], "options": turn["options"]})
    inv.messages = messages
    inv.state = turn["state"] or inv.state
    inv.status = "done" if turn["done"] else "active"
    flag_modified(inv, "messages")
    flag_modified(inv, "state")
    await db.commit()
    return {"message": turn["message"], "options": turn["options"],
            "input": turn["input"], "done": turn["done"]}
