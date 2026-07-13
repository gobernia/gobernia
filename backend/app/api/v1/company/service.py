"""Logo de la empresa del cliente: validación, normalización y acceso.

El logo vive en la tabla `company_logos` (bytes en la DB, no en S3).
Se re-guarda siempre como PNG de máx 600px de ancho, así que lo que sale de
`normalize_logo` es siempre un PNG válido y pequeño.
"""
import base64
from io import BytesIO

from PIL import Image
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.company_logo import CompanyLogo

ALLOWED_EXTENSIONS = {".png", ".jpg", ".jpeg"}
MAX_BYTES = 1024 * 1024          # 1 MB
MAX_WIDTH = 600                  # px
CONTENT_TYPE = "image/png"


class LogoError(ValueError):
    """Logo inválido (extensión, tamaño o contenido)."""


def _extension(filename: str | None) -> str:
    name = (filename or "").strip().lower()
    dot = name.rfind(".")
    return name[dot:] if dot != -1 else ""


def normalize_logo(raw: bytes, filename: str | None) -> bytes:
    """Valida y normaliza el logo. Devuelve PNG (<=600px de ancho).

    Lanza LogoError si la extensión no está permitida, pesa más de 1 MB, o el
    contenido no es una imagen de verdad (no basta con que se llame .png).
    """
    ext = _extension(filename)
    if ext not in ALLOWED_EXTENSIONS:
        raise LogoError("Formato no permitido. Usa PNG o JPG.")
    if not raw:
        raise LogoError("El archivo está vacío.")
    if len(raw) > MAX_BYTES:
        raise LogoError("El logo no puede pesar más de 1 MB.")

    # No confiamos en la extensión: Pillow tiene que poder abrir la imagen.
    try:
        probe = Image.open(BytesIO(raw))
        probe.verify()
    except Exception:
        raise LogoError("El archivo no es una imagen válida.")

    # verify() deja la imagen inutilizable: hay que reabrirla para procesarla.
    try:
        img = Image.open(BytesIO(raw))
        img = img.convert("RGBA")  # preserva transparencia
        if img.width > MAX_WIDTH:
            alto = max(1, round(img.height * MAX_WIDTH / img.width))
            img = img.resize((MAX_WIDTH, alto), Image.LANCZOS)
        out = BytesIO()
        img.save(out, format="PNG", optimize=True)
    except LogoError:
        raise
    except Exception:
        raise LogoError("No se pudo procesar la imagen.")

    return out.getvalue()


def to_data_url(data: bytes | None, content_type: str = CONTENT_TYPE) -> str | None:
    if not data:
        return None
    return f"data:{content_type};base64,{base64.b64encode(data).decode('ascii')}"


async def get_logo(user_id: str, db: AsyncSession) -> CompanyLogo | None:
    return (await db.execute(
        select(CompanyLogo).where(CompanyLogo.user_id == user_id)
    )).scalar_one_or_none()


async def get_logo_bytes(user_id: str, db: AsyncSession) -> bytes | None:
    """Bytes del logo (PNG) del usuario, o None. Nunca lanza: los PDFs se generan igual."""
    try:
        row = await get_logo(user_id, db)
    except Exception:
        return None
    return row.data if row is not None else None


async def get_logo_data_url(user_id: str, db: AsyncSession) -> str | None:
    row = await get_logo(user_id, db)
    if row is None:
        return None
    return to_data_url(row.data, row.content_type or CONTENT_TYPE)


async def upsert_logo(user_id: str, data: bytes, db: AsyncSession) -> CompanyLogo:
    """Reemplaza el logo anterior del usuario (un logo por usuario)."""
    row = await get_logo(user_id, db)
    if row is None:
        row = CompanyLogo(user_id=user_id, content_type=CONTENT_TYPE, data=data)
        db.add(row)
    else:
        row.content_type = CONTENT_TYPE
        row.data = data
    await db.flush()
    return row
