"""
Etapa 7 — Carga de Documentos
POST /{session_id}/etapa-7/upload    → sube un documento, crea registro, despacha tarea Celery
POST /{session_id}/etapa-7/complete  → confirma todos los docs subidos, marca etapa completa
"""
import os
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from sqlalchemy.orm.attributes import flag_modified

from app.core.dependencies import get_current_user_id, get_db
from app.models.document import Document
from app.models.onboarding_session import OnboardingSession
from app.schemas.etapa7 import (
    ALLOWED_EXTENSIONS,
    DOCUMENT_TYPE_LABELS,
    MAX_FILE_SIZE_BYTES,
    DocumentMeta,
    DocumentUploadResponse,
    Etapa7Output,
)
from app.services.documents.storage import generate_storage_key, upload_to_storage

router = APIRouter()


async def _get_session_or_404(
    session_id: uuid.UUID,
    user_id: str,
    db: AsyncSession,
) -> OnboardingSession:
    result = await db.execute(
        select(OnboardingSession).where(
            OnboardingSession.id == session_id,
            OnboardingSession.user_id == user_id,
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Sesión no encontrada")
    return session


def _validate_file(file: UploadFile, content: bytes) -> None:
    ext = Path(file.filename or "").suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Tipo de archivo no permitido '{ext}'. Permitidos: {', '.join(ALLOWED_EXTENSIONS)}",
        )
    if len(content) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"El archivo supera el tamaño máximo de 10 MB.",
        )


@router.post("/{session_id}/etapa-7/upload", response_model=DocumentUploadResponse)
async def upload_document(
    session_id: uuid.UUID,
    file: UploadFile = File(...),
    document_type: str = Form(...),
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Sube un documento al repositorio y despacha su procesamiento asíncrono."""
    session = await _get_session_or_404(session_id, user_id, db)

    if 6 not in (session.completed_stages or []):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Debes completar la Etapa 6 antes de continuar.",
        )

    content = await file.read()
    _validate_file(file, content)

    doc_id = uuid.uuid4()
    filename = file.filename or f"document_{doc_id}"
    s3_key = generate_storage_key(session_id, doc_id, filename)

    # Subir a almacenamiento (no bloquea si no hay credenciales)
    await upload_to_storage(content, s3_key)

    # Crear registro en DB
    document = Document(
        id=doc_id,
        session_id=session_id,
        user_id=user_id,
        document_type=document_type,
        filename=filename,
        s3_key=s3_key,
        processing_status="pending",
    )
    db.add(document)

    # Actualizar Memory Buffer con metadata del documento
    buf = dict(session.memory_buffer or {})
    docs_list = list(buf.get("documents", []))
    docs_list.append({
        "document_id": str(doc_id),
        "filename": filename,
        "document_type": document_type,
        "file_size_kb": round(len(content) / 1024, 1),
        "status": "pending",
    })
    buf["documents"] = docs_list
    session.memory_buffer = buf
    flag_modified(session, "memory_buffer")

    await db.flush()
    await db.commit()

    # Despachar tarea Celery (no bloquea el response)
    try:
        from app.tasks.document_tasks import process_document_task
        process_document_task.delay(str(doc_id))
    except Exception:
        pass  # Si Celery/Redis no están disponibles en dev, continúa sin error

    return DocumentUploadResponse(
        document_id=str(doc_id),
        session_id=str(session_id),
        filename=filename,
        document_type=document_type,
        document_type_label=DOCUMENT_TYPE_LABELS.get(document_type, document_type),
        status="pending",
        file_size_kb=round(len(content) / 1024, 1),
        message="Documento recibido. El análisis estará disponible en breve.",
    )


@router.post("/{session_id}/etapa-7/complete", response_model=Etapa7Output)
async def complete_etapa7(
    session_id: uuid.UUID,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Confirma que el usuario terminó de subir documentos y marca la etapa como completa."""
    session = await _get_session_or_404(session_id, user_id, db)

    if 6 not in (session.completed_stages or []):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Debes completar la Etapa 6 antes de continuar.",
        )

    buf = session.memory_buffer or {}
    documents_meta = buf.get("documents", [])

    if not documents_meta:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Debes subir al menos un documento antes de completar esta etapa.",
        )

    completed = list(session.completed_stages or [])
    if 7 not in completed:
        completed.append(7)
    session.completed_stages = completed

    await db.flush()
    await db.commit()

    docs = [
        DocumentMeta(
            document_id=d["document_id"],
            filename=d["filename"],
            document_type=d["document_type"],
            document_type_label=DOCUMENT_TYPE_LABELS.get(d["document_type"], d["document_type"]),
            file_size_kb=d["file_size_kb"],
            status=d["status"],
        )
        for d in documents_meta
    ]

    return Etapa7Output(
        session_id=str(session.id),
        completed_stages=completed,
        document_count=len(docs),
        documents=docs,
        next_stage=8,
    )
