import secrets
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.core.dependencies import get_current_user_id, get_db
from app.models.perspectiva_invite import PerspectivaInvite
from app.models.onboarding_session import OnboardingSession
from app.models.diagnostico_estrategico import DiagnosticoEstrategico
from app.schemas.perspectivas import InviteIn, InviteOut, InviteListItem

router = APIRouter()


async def _empresa_ctx_for(owner_user_id: str, db: AsyncSession) -> str:
    onb = (await db.execute(
        select(OnboardingSession).where(OnboardingSession.user_id == owner_user_id)
        .order_by(OnboardingSession.created_at.desc())
    )).scalars().first()
    c = (((onb.memory_buffer if onb else {}) or {}).get("company") or {})
    partes = [str(c[k]) for k in ("name", "industry") if c.get(k)]
    return " · ".join(partes)


def _invite_url(token: str) -> str:
    return f"/p/{token}"


@router.post("/perspectivas/invite", response_model=InviteOut)
async def crear_invite(
    body: InviteIn,
    user_id: str = Depends(get_current_user_id), db: AsyncSession = Depends(get_db),
):
    token = secrets.token_urlsafe(16)
    inv = PerspectivaInvite(
        owner_user_id=user_id, role=body.role,
        invitee_name=(body.name or None), token=token,
        status="pending", messages=[], state={},
    )
    db.add(inv)
    await db.flush()
    await db.commit()
    return InviteOut(
        id=str(inv.id), role=inv.role, invitee_name=inv.invitee_name, token=token,
        url=_invite_url(token), status=inv.status, created_at=inv.created_at,
    )


@router.get("/perspectivas", response_model=list[InviteListItem])
async def listar_invites(
    user_id: str = Depends(get_current_user_id), db: AsyncSession = Depends(get_db),
):
    rows = (await db.execute(
        select(PerspectivaInvite).where(PerspectivaInvite.owner_user_id == user_id)
        .order_by(PerspectivaInvite.created_at.desc())
    )).scalars().all()
    return [InviteListItem(id=str(r.id), role=r.role, invitee_name=r.invitee_name,
                           token=r.token, status=r.status, created_at=r.created_at) for r in rows]


@router.delete("/perspectivas/{invite_id}")
async def revocar_invite(
    invite_id: uuid.UUID,
    user_id: str = Depends(get_current_user_id), db: AsyncSession = Depends(get_db),
):
    inv = (await db.execute(
        select(PerspectivaInvite).where(
            PerspectivaInvite.id == invite_id, PerspectivaInvite.owner_user_id == user_id)
    )).scalar_one_or_none()
    if inv is None:
        raise HTTPException(status_code=404, detail="Invitación no encontrada")
    await db.delete(inv)
    await db.commit()
    return {"deleted": True}


@router.post("/perspectivas/consolidar")
async def consolidar(
    user_id: str = Depends(get_current_user_id), db: AsyncSession = Depends(get_db),
):
    diag = (await db.execute(
        select(DiagnosticoEstrategico).where(DiagnosticoEstrategico.user_id == user_id)
        .order_by(DiagnosticoEstrategico.created_at.desc())
    )).scalars().first()
    if diag is None:
        raise HTTPException(status_code=404, detail="Genera tu diagnóstico antes de consolidar.")
    content = dict(diag.content or {})
    content["perspectivas"] = {**(content.get("perspectivas") or {}), "status": "generating"}
    diag.content = content
    flag_modified(diag, "content")
    await db.commit()
    try:
        from app.tasks.perspectivas_tasks import generate_perspectivas_task
        generate_perspectivas_task.delay(user_id)
    except Exception:
        content["perspectivas"]["status"] = "failed"
        diag.content = content
        flag_modified(diag, "content")
        await db.commit()
    return {"ok": True}


@router.get("/perspectivas/sintesis")
async def get_sintesis(
    user_id: str = Depends(get_current_user_id), db: AsyncSession = Depends(get_db),
):
    diag = (await db.execute(
        select(DiagnosticoEstrategico).where(DiagnosticoEstrategico.user_id == user_id)
        .order_by(DiagnosticoEstrategico.created_at.desc())
    )).scalars().first()
    p = ((diag.content if diag else {}) or {}).get("perspectivas") or {}
    return {"status": p.get("status") or "none",
            "coincidencias": p.get("coincidencias") or [],
            "contradicciones": p.get("contradicciones") or [],
            "puntos_ciegos": p.get("puntos_ciegos") or [],
            "por_rol": p.get("por_rol") or {},
            "conteo": p.get("conteo") or {}}
