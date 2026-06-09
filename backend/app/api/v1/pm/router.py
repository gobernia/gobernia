from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.core.dependencies import get_current_user_id, get_db
from app.models.compromiso import Compromiso
from app.schemas.pm import AvanceIn, CompromisoOut, CompromisoPublicOut, ResponsablePatch
from app.services.governance.pm import nudge_estado

router = APIRouter()


def _ref_date(c: Compromiso) -> date:
    av = c.avances or []
    if av:
        try:
            return date.fromisoformat(av[-1]["fecha"])
        except (KeyError, ValueError, TypeError):
            pass
    return c.created_at.date() if c.created_at else date.today()


def _out(c: Compromiso, today: date) -> CompromisoOut:
    return CompromisoOut(
        id=str(c.id), descripcion=c.descripcion,
        responsable_email=c.responsable_email, responsable_nombre=c.responsable_nombre,
        fecha_compromiso=c.fecha_compromiso.isoformat() if c.fecha_compromiso else None,
        status=c.status, nudge=nudge_estado(c.status, _ref_date(c), c.fecha_compromiso, today),
        token=c.token, avances=c.avances or [],
    )


def _public_out(c: Compromiso) -> CompromisoPublicOut:
    return CompromisoPublicOut(
        descripcion=c.descripcion,
        fecha_compromiso=c.fecha_compromiso.isoformat() if c.fecha_compromiso else None,
        status=c.status, avances=c.avances or [],
    )


@router.get("/pm/compromisos", response_model=list[CompromisoOut])
async def list_compromisos(
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    res = await db.execute(
        select(Compromiso).where(Compromiso.user_id == user_id).order_by(Compromiso.created_at.desc())
    )
    today = date.today()
    return [_out(c, today) for c in res.scalars().all()]


@router.patch("/pm/compromisos/{compromiso_id}", response_model=CompromisoOut)
async def patch_compromiso(
    compromiso_id: str,
    body: ResponsablePatch,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    res = await db.execute(select(Compromiso).where(Compromiso.id == compromiso_id))
    c = res.scalar_one_or_none()
    if c is None or c.user_id != user_id:
        raise HTTPException(status_code=404, detail="Compromiso no encontrado.")
    if body.responsable_email is not None:
        c.responsable_email = body.responsable_email
    if body.responsable_nombre is not None:
        c.responsable_nombre = body.responsable_nombre
    if body.fecha_compromiso is not None:
        c.fecha_compromiso = date.fromisoformat(body.fecha_compromiso)
    return _out(c, date.today())


@router.get("/pm/c/{token}", response_model=CompromisoPublicOut)
async def get_compromiso_publico(token: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Compromiso).where(Compromiso.token == token))
    c = res.scalar_one_or_none()
    if c is None:
        raise HTTPException(status_code=404, detail="Compromiso no encontrado.")
    return _public_out(c)


@router.post("/pm/c/{token}/avance", response_model=CompromisoPublicOut)
async def reportar_avance(token: str, body: AvanceIn, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Compromiso).where(Compromiso.token == token))
    c = res.scalar_one_or_none()
    if c is None:
        raise HTTPException(status_code=404, detail="Compromiso no encontrado.")
    avances = list(c.avances or [])
    avances.append({
        "fecha": date.today().isoformat(), "pct": body.pct,
        "nota": body.nota, "evidencia_url": body.evidencia_url,
    })
    c.avances = avances
    flag_modified(c, "avances")
    if body.pct >= 100:
        c.status = "completado"
    elif body.pct > 0 and c.status != "completado":
        c.status = "en_progreso"
    return _public_out(c)
