import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user_id, get_db
from app.models.evidence import Evidence
from app.schemas.evidence import EvidenceOut
from app.schemas.etapa7 import ALLOWED_EXTENSIONS, MAX_FILE_SIZE_BYTES
from app.services.documents.storage import generate_storage_key, upload_to_storage
from app.api.v1.action_plans.router import _get_user_task_or_404

router = APIRouter()


def _validate_file(filename: str, content: bytes) -> None:
    ext = Path(filename or "").suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Tipo de archivo no permitido '{ext}'. Permitidos: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
        )
    if len(content) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El archivo supera el tamaño máximo de 10 MB.",
        )


def _evidence_out(e: Evidence) -> EvidenceOut:
    return EvidenceOut(
        id=str(e.id), action_task_id=str(e.action_task_id), filename=e.filename,
        content_type=e.content_type, size_bytes=e.size_bytes, created_at=e.created_at,
    )


@router.post("/tasks/{task_id}/evidence", response_model=EvidenceOut)
async def upload_evidence(
    task_id: uuid.UUID,
    file: UploadFile = File(...),
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    task = await _get_user_task_or_404(task_id, user_id, db)
    content = await file.read()
    _validate_file(file.filename or "", content)

    ev_id = uuid.uuid4()
    filename = file.filename or f"evidence_{ev_id}"
    s3_key = generate_storage_key(task_id, ev_id, filename)
    await upload_to_storage(content, s3_key)

    ev = Evidence(
        id=ev_id, action_task_id=task_id, filename=filename, s3_key=s3_key,
        content_type=file.content_type or "application/octet-stream",
        size_bytes=len(content),
    )
    db.add(ev)
    if task.status == "pendiente":
        task.status = "en_progreso"
    await db.flush()
    await db.commit()
    await db.refresh(ev)
    return _evidence_out(ev)


@router.get("/tasks/{task_id}/evidence", response_model=list[EvidenceOut])
async def list_evidence(
    task_id: uuid.UUID,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    await _get_user_task_or_404(task_id, user_id, db)
    res = await db.execute(
        select(Evidence).where(Evidence.action_task_id == task_id).order_by(Evidence.created_at)
    )
    return [_evidence_out(e) for e in res.scalars().all()]


@router.delete("/evidence/{evidence_id}", status_code=204)
async def delete_evidence(
    evidence_id: uuid.UUID,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    res = await db.execute(select(Evidence).where(Evidence.id == evidence_id))
    ev = res.scalar_one_or_none()
    if not ev:
        raise HTTPException(status_code=404, detail="Evidencia no encontrada")
    await _get_user_task_or_404(ev.action_task_id, user_id, db)
    await db.delete(ev)
    await db.commit()
