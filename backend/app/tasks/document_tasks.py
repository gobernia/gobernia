"""
Tarea Celery: procesa un documento subido en Etapa 7.
Descarga el archivo de S3, extrae texto, llama a Claude y actualiza el registro.
"""
import asyncio
import uuid

from app.tasks.worker import celery_app


@celery_app.task(name="process_document", bind=True, max_retries=3)
def process_document_task(self, document_id: str) -> dict:
    """
    Corre en el worker de Celery (proceso separado, contexto síncrono).
    Crea su propia sesión de DB para no compartir estado con FastAPI.
    """
    try:
        return asyncio.run(_process(document_id))
    except Exception as exc:
        raise self.retry(exc=exc, countdown=60)


async def _process(document_id: str) -> dict:
    from sqlalchemy import select
    from app.db.session import task_session
    from app.models.document import Document
    from app.services.documents.processor import (
        analyze_document_with_claude,
        extract_text_from_content,
    )
    import boto3
    from app.core.config import settings

    async with task_session() as db:
        result = await db.execute(
            select(Document).where(Document.id == uuid.UUID(document_id))
        )
        doc = result.scalar_one_or_none()
        if not doc:
            return {"status": "not_found"}

        doc.processing_status = "processing"
        await db.commit()

        # Descargar desde S3 (si hay credenciales)
        content = b""
        if settings.AWS_ACCESS_KEY_ID:
            s3 = boto3.client(
                "s3",
                aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                region_name=settings.AWS_REGION,
            )
            obj = s3.get_object(Bucket=settings.S3_BUCKET_DOCUMENTS, Key=doc.s3_key)
            content = obj["Body"].read()

        # Extraer texto y analizar
        text = extract_text_from_content(content, "application/pdf")
        insights = analyze_document_with_claude(text, doc.document_type, "")

        doc.agent_insights = insights
        doc.processing_status = "completed"
        await db.commit()

        return {"status": "completed", "document_id": document_id}
