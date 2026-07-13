"""
Abstracción de almacenamiento de documentos.
En producción sube a S3. En desarrollo/tests devuelve la clave sin subir nada.
"""
import uuid

from app.core.config import settings


def generate_storage_key(session_id: uuid.UUID, doc_id: uuid.UUID, filename: str) -> str:
    return f"documents/{session_id}/{doc_id}/{filename}"


def _s3_client():
    import boto3  # lazy — no instalar en dev si no se usa S3
    kwargs = {
        "aws_access_key_id": settings.AWS_ACCESS_KEY_ID,
        "aws_secret_access_key": settings.AWS_SECRET_ACCESS_KEY,
        "region_name": settings.AWS_REGION,
    }
    # Endpoint personalizado (Supabase Storage u otro compatible-S3); vacío → AWS S3.
    if settings.S3_ENDPOINT_URL:
        kwargs["endpoint_url"] = settings.S3_ENDPOINT_URL
    return boto3.client("s3", **kwargs)


async def upload_to_storage(
    content: bytes,
    key: str,
) -> str:
    """Sube el archivo a S3. Si no hay credenciales configuradas, devuelve la clave sin subir."""
    if not settings.AWS_ACCESS_KEY_ID:
        return key

    _s3_client().put_object(
        Bucket=settings.S3_BUCKET_DOCUMENTS,
        Key=key,
        Body=content,
    )
    return key


def download_from_storage(key: str) -> bytes | None:
    """Descarga el objeto de S3. Sin credenciales o ante cualquier fallo → None (no rompe el cierre)."""
    if not settings.AWS_ACCESS_KEY_ID:
        return None
    try:
        obj = _s3_client().get_object(Bucket=settings.S3_BUCKET_DOCUMENTS, Key=key)
        return obj["Body"].read()
    except Exception:
        return None


def delete_from_storage(key: str) -> bool:
    """Borra el objeto del storage. Sin credenciales o ante cualquier fallo → False (no rompe el borrado en DB)."""
    if not settings.AWS_ACCESS_KEY_ID:
        return False
    try:
        _s3_client().delete_object(Bucket=settings.S3_BUCKET_DOCUMENTS, Key=key)
        return True
    except Exception:
        return False


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
