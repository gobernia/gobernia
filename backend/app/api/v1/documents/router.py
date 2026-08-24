"""
Router de documentos — el repositorio general del usuario (perfil base).

Da servicio a la pestaña "Mis consejeros": subir, listar y eliminar los
documentos que alimentan los análisis de los consejeros. A diferencia del
upload de la Etapa 7 (onboarding), aquí NO se exige haber llegado a la
etapa 6: el usuario puede nutrir a su Consejo en cualquier momento.
"""
import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.api.v1.onboarding.etapa7 import _validate_file
from app.core.dependencies import get_current_user_id, get_db
from app.models.document import Document
from app.models.onboarding_session import OnboardingSession
from app.schemas.etapa7 import DOCUMENT_TYPE_LABELS, DocumentUploadResponse
from app.services.documents.storage import delete_from_storage, generate_storage_key, upload_to_storage

router = APIRouter()


async def _latest_onboarding_or_400(user_id: str, db: AsyncSession) -> OnboardingSession:
    res = await db.execute(
        select(OnboardingSession)
        .where(OnboardingSession.user_id == user_id)
        .order_by(OnboardingSession.created_at.desc())
        .limit(1)
    )
    session = res.scalars().first()
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Primero configura tu empresa con Todd para poder subir documentos.",
        )
    return session


@router.get("")
async def list_documents(
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Los documentos del repositorio del usuario (sin los de sesiones de Consejo)."""
    res = await db.execute(
        select(Document)
        .where(Document.user_id == user_id, Document.board_session_id.is_(None))
        .order_by(Document.created_at.desc())
    )
    return {
        "items": [
            {
                "document_id": str(d.id),
                "filename": d.filename,
                "document_type": d.document_type,
                "document_type_label": DOCUMENT_TYPE_LABELS.get(d.document_type, d.document_type),
                "status": d.processing_status,
                "created_at": d.created_at.isoformat() if d.created_at else None,
            }
            for d in res.scalars().all()
        ],
        "types": [{"value": k, "label": v} for k, v in DOCUMENT_TYPE_LABELS.items()],
    }


@router.post("/upload", response_model=DocumentUploadResponse)
async def upload_document(
    file: UploadFile = File(...),
    document_type: str = Form(...),
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Sube un documento al repositorio del usuario y despacha su procesamiento."""
    if document_type not in DOCUMENT_TYPE_LABELS:
        raise HTTPException(status_code=400, detail="Tipo de documento inválido.")

    session = await _latest_onboarding_or_400(user_id, db)

    content = await file.read()
    _validate_file(file, content)

    doc_id = uuid.uuid4()
    filename = file.filename or f"document_{doc_id}"
    s3_key = generate_storage_key(session.id, doc_id, filename)
    await upload_to_storage(content, s3_key)

    document = Document(
        id=doc_id,
        session_id=session.id,
        user_id=user_id,
        document_type=document_type,
        filename=filename,
        s3_key=s3_key,
        processing_status="pending",
    )
    db.add(document)

    # Registrar en el memory buffer (los consejeros leen esta lista).
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

    try:
        from app.tasks.document_tasks import process_document_task
        process_document_task.delay(str(doc_id))
    except Exception:
        pass  # Si Celery/Redis no están disponibles en dev, continúa sin error

    return DocumentUploadResponse(
        document_id=str(doc_id),
        session_id=str(session.id),
        filename=filename,
        document_type=document_type,
        document_type_label=DOCUMENT_TYPE_LABELS.get(document_type, document_type),
        status="pending",
        file_size_kb=round(len(content) / 1024, 1),
        message="Documento recibido. Tus consejeros lo tendrán disponible en breve.",
    )


@router.delete("/{document_id}", status_code=204)
async def delete_document(
    document_id: uuid.UUID,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Elimina un documento del repositorio (registro + archivo en storage)."""
    res = await db.execute(
        select(Document).where(Document.id == document_id, Document.user_id == user_id)
    )
    doc = res.scalar_one_or_none()
    if doc is None:
        raise HTTPException(status_code=404, detail="Documento no encontrado.")

    try:
        delete_from_storage(doc.s3_key)
    except Exception:
        pass  # Si el archivo ya no existe en storage, igual borramos el registro.

    await db.delete(doc)
    await db.commit()


@router.get("/status")
async def documents_status(user_id: str = Depends(get_current_user_id)):
    return {"status": "ready"}
