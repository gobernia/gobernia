"""
Abstracción de almacenamiento de documentos.
En producción sube a S3. En desarrollo/tests devuelve la clave sin subir nada.
"""
import uuid

from app.core.config import settings


def generate_storage_key(session_id: uuid.UUID, doc_id: uuid.UUID, filename: str) -> str:
    return f"documents/{session_id}/{doc_id}/{filename}"


async def upload_to_storage(
    content: bytes,
    key: str,
) -> str:
    """Sube el archivo a S3. Si no hay credenciales configuradas, devuelve la clave sin subir."""
    if not settings.AWS_ACCESS_KEY_ID:
        return key

    import boto3  # lazy — no instalar en dev si no se usa S3
    s3 = boto3.client(
        "s3",
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        region_name=settings.AWS_REGION,
    )
    s3.put_object(
        Bucket=settings.S3_BUCKET_DOCUMENTS,
        Key=key,
        Body=content,
    )
    return key
