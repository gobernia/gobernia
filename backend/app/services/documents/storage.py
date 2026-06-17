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


def _s3_client():
    import boto3  # lazy — no instalar en dev si no se usa S3
    return boto3.client(
        "s3",
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        region_name=settings.AWS_REGION,
    )


def download_from_storage(key: str) -> bytes | None:
    """Descarga el objeto de S3. Sin credenciales o ante cualquier fallo → None (no rompe el cierre)."""
    if not settings.AWS_ACCESS_KEY_ID:
        return None
    try:
        obj = _s3_client().get_object(Bucket=settings.S3_BUCKET_DOCUMENTS, Key=key)
        return obj["Body"].read()
    except Exception:
        return None


def presigned_get_url(key: str, expires: int = 300) -> str | None:
    """URL GET prefirmada y temporal. Sin credenciales o ante fallo → None."""
    if not settings.AWS_ACCESS_KEY_ID:
        return None
    try:
        return _s3_client().generate_presigned_url(
            "get_object",
            Params={"Bucket": settings.S3_BUCKET_DOCUMENTS, "Key": key},
            ExpiresIn=expires,
        )
    except Exception:
        return None
