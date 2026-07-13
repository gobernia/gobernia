"""Validación y normalización del logo del cliente (extensión, tamaño, contenido real, resize)."""
from io import BytesIO

import pytest
from PIL import Image

from app.api.v1.company.service import LogoError, MAX_WIDTH, normalize_logo, to_data_url


def _png(width: int = 100, height: int = 100) -> bytes:
    buf = BytesIO()
    Image.new("RGBA", (width, height), (10, 20, 30, 255)).save(buf, format="PNG")
    return buf.getvalue()


def _jpg(width: int = 100, height: int = 100) -> bytes:
    buf = BytesIO()
    Image.new("RGB", (width, height), (10, 20, 30)).save(buf, format="JPEG")
    return buf.getvalue()


def test_extension_no_permitida():
    with pytest.raises(LogoError):
        normalize_logo(_png(), "logo.gif")
    with pytest.raises(LogoError):
        normalize_logo(_png(), "logo.svg")
    with pytest.raises(LogoError):
        normalize_logo(_png(), "logo")


def test_extensiones_permitidas():
    assert normalize_logo(_png(), "logo.png").startswith(b"\x89PNG")
    assert normalize_logo(_jpg(), "logo.jpg").startswith(b"\x89PNG")
    assert normalize_logo(_jpg(), "LOGO.JPEG").startswith(b"\x89PNG")


def test_mayor_a_1mb_falla():
    grande = b"\x89PNG\r\n\x1a\n" + b"x" * (1024 * 1024 + 1)
    with pytest.raises(LogoError):
        normalize_logo(grande, "logo.png")


def test_archivo_que_no_es_imagen_aunque_se_llame_png():
    with pytest.raises(LogoError):
        normalize_logo(b"no soy un png, solo lo finjo", "logo.png")


def test_archivo_vacio():
    with pytest.raises(LogoError):
        normalize_logo(b"", "logo.png")


def test_redimensiona_a_600_de_ancho_manteniendo_proporcion():
    out = normalize_logo(_png(2000, 1000), "logo.png")
    img = Image.open(BytesIO(out))
    assert img.width == MAX_WIDTH
    assert img.height == 300  # 2000x1000 → 600x300
    assert img.format == "PNG"


def test_no_agranda_imagenes_pequenas():
    out = normalize_logo(_png(120, 40), "logo.png")
    img = Image.open(BytesIO(out))
    assert (img.width, img.height) == (120, 40)


def test_preserva_transparencia():
    buf = BytesIO()
    Image.new("RGBA", (50, 50), (255, 0, 0, 0)).save(buf, format="PNG")
    img = Image.open(BytesIO(normalize_logo(buf.getvalue(), "logo.png")))
    assert img.mode == "RGBA"
    assert img.getpixel((0, 0))[3] == 0  # sigue siendo transparente


def test_to_data_url():
    assert to_data_url(None) is None
    assert to_data_url(b"") is None
    assert to_data_url(_png(), "image/png").startswith("data:image/png;base64,")


@pytest.mark.asyncio
async def test_upsert_no_duplica_reemplaza_el_logo_anterior():
    """Subir dos veces deja UN solo registro: el segundo pisa los bytes del primero."""
    from unittest.mock import AsyncMock, MagicMock
    from app.api.v1.company.service import upsert_logo
    from app.models.company_logo import CompanyLogo

    guardados: list[CompanyLogo] = []

    db = AsyncMock()
    db.add = MagicMock(side_effect=guardados.append)
    db.flush = AsyncMock()

    async def _execute(_stmt):
        res = MagicMock()
        res.scalar_one_or_none.return_value = guardados[0] if guardados else None
        return res

    db.execute = AsyncMock(side_effect=_execute)

    primero = await upsert_logo("u1", b"AAA", db)
    segundo = await upsert_logo("u1", b"BBB", db)

    assert len(guardados) == 1        # solo se insertó una fila
    assert primero is segundo         # la segunda subida actualizó la misma
    assert segundo.data == b"BBB"
    assert segundo.user_id == "u1"
