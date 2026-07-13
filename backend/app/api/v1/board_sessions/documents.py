"""
Board pack de la sesión de consejo — documentos que leerán los agentes.

POST   /board-sessions/{id}/documents            → sube un documento del periodo
GET    /board-sessions/{id}/documents            → lista los documentos de la sesión
DELETE /board-sessions/{id}/documents/{doc_id}   → borra un documento de la sesión
"""
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user_id, get_db
from app.models.board_session import BoardSession
from app.models.document import Document
from app.schemas.board_session import BoardDocumentList, BoardDocumentOut
from app.schemas.etapa7 import (
    ALLOWED_EXTENSIONS,
    DOCUMENT_TYPE_LABELS,
    MAX_FILE_SIZE_BYTES,
    MAX_FILE_SIZE_MB,
)
from app.services.documents.storage import (
    delete_from_storage,
    generate_storage_key,
    upload_to_storage,
)

router = APIRouter()


async def _get_board_session_owned(
    board_session_id: uuid.UUID, user_id: str, db: AsyncSession
) -> BoardSession:
    """404 si no existe; 403 si es de otro usuario."""
    result = await db.execute(
        select(BoardSession).where(BoardSession.id == board_session_id)
    )
    bs = result.scalar_one_or_none()
    if not bs:
        raise HTTPException(status_code=404, detail="Sesión de consejo no encontrada.")
    if bs.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes acceso a esta sesión de consejo.",
        )
    return bs


def _validate_upload(filename: str | None, document_type: str, content: bytes) -> None:
    ext = Path(filename or "").suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Tipo de archivo no permitido '{ext}'. Permitidos: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
        )
    if len(content) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"El archivo supera el tamaño máximo de {MAX_FILE_SIZE_MB} MB.",
        )
    if document_type not in DOCUMENT_TYPE_LABELS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Tipo de documento no válido '{document_type}'. "
                   f"Válidos: {', '.join(DOCUMENT_TYPE_LABELS)}",
        )


def _to_out(doc: Document) -> BoardDocumentOut:
    return BoardDocumentOut(
        id=str(doc.id),
        filename=doc.filename,
        document_type=doc.document_type,
        document_type_label=DOCUMENT_TYPE_LABELS.get(doc.document_type, doc.document_type),
        created_at=doc.created_at,
    )


@router.post("/{board_session_id}/documents", response_model=BoardDocumentOut,
             status_code=status.HTTP_201_CREATED)
async def upload_board_document(
    board_session_id: uuid.UUID,
    file: UploadFile = File(...),
    document_type: str = Form(...),
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Sube un documento al board pack de la sesión. Los agentes lo leerán en /analyse."""
    bs = await _get_board_session_owned(board_session_id, user_id, db)

    content = await file.read()
    _validate_upload(file.filename, document_type, content)

    doc_id = uuid.uuid4()
    filename = file.filename or f"document_{doc_id}"
    s3_key = generate_storage_key(board_session_id, doc_id, filename)
    await upload_to_storage(content, s3_key)

    document = Document(
        id=doc_id,
        session_id=bs.onboarding_session_id,
        board_session_id=board_session_id,
        user_id=user_id,
        document_type=document_type,
        filename=filename,
        s3_key=s3_key,
        processing_status="pending",
    )
    db.add(document)
    await db.flush()
    await db.commit()

    return _to_out(document)


@router.get("/{board_session_id}/documents", response_model=BoardDocumentList)
async def list_board_documents(
    board_session_id: uuid.UUID,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Lista los documentos del board pack de la sesión."""
    await _get_board_session_owned(board_session_id, user_id, db)

    result = await db.execute(
        select(Document)
        .where(Document.board_session_id == board_session_id)
        .order_by(Document.created_at)
    )
    docs = result.scalars().all()
    return BoardDocumentList(items=[_to_out(d) for d in docs])


@router.delete("/{board_session_id}/documents/{document_id}")
async def delete_board_document(
    board_session_id: uuid.UUID,
    document_id: uuid.UUID,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Borra un documento del board pack (fila + objeto en storage, si se puede)."""
    await _get_board_session_owned(board_session_id, user_id, db)

    result = await db.execute(
        select(Document).where(
            Document.id == document_id,
            Document.board_session_id == board_session_id,
        )
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Documento no encontrado en esta sesión.")

    s3_key = doc.s3_key
    await db.delete(doc)
    await db.commit()

    # El borrado remoto es best-effort: si falla, la fila ya no existe y no rompemos la request.
    delete_from_storage(s3_key)

    return {"deleted": True, "document_id": str(document_id)}
