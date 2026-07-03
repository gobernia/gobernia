from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user_id, get_db
from app.models.diagnostico_estrategico import DiagnosticoEstrategico
from app.models.onboarding_session import OnboardingSession
from app.schemas.diagnostico import DiagnosticoOut, DiagnosticoStatusOut
from app.services.data_completeness import missing_diagnostico_data
from app.services.pdf.diagnostico_pdf import build_diagnostico_pdf

router = APIRouter()

_GENERATING_TIMEOUT = timedelta(minutes=20)


async def _current(user_id: str, db: AsyncSession) -> DiagnosticoEstrategico | None:
    return (await db.execute(
        select(DiagnosticoEstrategico).where(DiagnosticoEstrategico.user_id == user_id)
        .order_by(DiagnosticoEstrategico.created_at.desc())
    )).scalars().first()


async def _expire_if_stale(diag: DiagnosticoEstrategico | None, db: AsyncSession):
    if (diag is not None and diag.status == "generating" and diag.created_at is not None
            and datetime.now(timezone.utc) - diag.created_at > _GENERATING_TIMEOUT):
        diag.status = "failed"
        diag.fail_reason = "error"
        await db.commit()
    return diag


async def _memory_buffer(user_id: str, db: AsyncSession) -> dict:
    onb = (await db.execute(
        select(OnboardingSession).where(OnboardingSession.user_id == user_id)
        .order_by(OnboardingSession.created_at.desc())
    )).scalars().first()
    return (onb.memory_buffer if onb else {}) or {}


@router.post("/diagnostico/generate", response_model=DiagnosticoStatusOut)
async def generate_diagnostico_endpoint(
    user_id: str = Depends(get_current_user_id), db: AsyncSession = Depends(get_db),
):
    mb = await _memory_buffer(user_id, db)
    faltantes = missing_diagnostico_data(mb)
    if faltantes:
        raise HTTPException(
            status_code=400,
            detail="Para generar el diagnóstico necesitas completar: " + "; ".join(faltantes) + ".",
        )

    existing = await _expire_if_stale(await _current(user_id, db), db)
    if existing and existing.status == "generating":
        return DiagnosticoStatusOut(status="generating")
    if existing is not None:
        await db.delete(existing)
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
        diag.fail_reason = "error"
        await db.commit()
        raise HTTPException(status_code=503, detail="No se pudo iniciar la generación del diagnóstico.")

    return DiagnosticoStatusOut(status="generating")


@router.get("/diagnostico/status", response_model=DiagnosticoStatusOut)
async def diagnostico_status(
    user_id: str = Depends(get_current_user_id), db: AsyncSession = Depends(get_db),
):
    diag = await _expire_if_stale(await _current(user_id, db), db)
    if not diag:
        raise HTTPException(status_code=404, detail="No hay diagnóstico generado.")
    return DiagnosticoStatusOut(status=diag.status, fail_reason=diag.fail_reason)


@router.get("/diagnostico", response_model=DiagnosticoOut)
async def get_diagnostico(
    user_id: str = Depends(get_current_user_id), db: AsyncSession = Depends(get_db),
):
    diag = await _expire_if_stale(await _current(user_id, db), db)
    if not diag:
        raise HTTPException(status_code=404, detail="No hay diagnóstico generado.")
    content = diag.content or {}
    return DiagnosticoOut(
        status=diag.status, fail_reason=diag.fail_reason,
        sections=content.get("sections", []), sources=content.get("sources", []),
        fortalezas_debilidades=content.get("fortalezas_debilidades", {}),
        riesgos=content.get("riesgos", []),
    )


@router.get("/diagnostico/pdf")
async def diagnostico_pdf(
    user_id: str = Depends(get_current_user_id), db: AsyncSession = Depends(get_db),
):
    diag = await _current(user_id, db)
    if not diag or diag.status != "active" or not diag.content:
        raise HTTPException(status_code=404, detail="No hay diagnóstico disponible.")
    mb = await _memory_buffer(user_id, db)
    company_name = ((mb.get("company") or {}).get("name"))
    pdf = build_diagnostico_pdf(diag.content, company_name)
    return Response(
        content=pdf, media_type="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="diagnostico.pdf"'},
    )
