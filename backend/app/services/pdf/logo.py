"""Helper compartido para pintar el logo del cliente en los PDFs.

Regla de oro: si no hay logo o los bytes están corruptos, el PDF se genera igual
(sin logo, sin excepción). Todas las funciones de aquí son a prueba de fallos.
"""
from io import BytesIO

from reportlab.lib.units import cm
from reportlab.lib.utils import ImageReader
from reportlab.platypus import Image


def _reader(logo: bytes | None) -> ImageReader | None:
    if not logo:
        return None
    try:
        reader = ImageReader(BytesIO(logo))
        w, h = reader.getSize()
        if not w or not h:
            return None
        return reader
    except Exception:
        return None


def logo_flowable(logo: bytes | None, height_cm: float = 1.2) -> Image | None:
    """Image de reportlab con alto fijo y ancho proporcional, o None si no se puede."""
    reader = _reader(logo)
    if reader is None:
        return None
    try:
        w, h = reader.getSize()
        alto = height_cm * cm
        ancho = alto * (w / h)
        img = Image(BytesIO(logo), width=ancho, height=alto)
        img.hAlign = "LEFT"
        return img
    except Exception:
        return None


def draw_logo(canv, logo: bytes | None, x: float, y: float, max_h: float,
              max_w: float | None = None) -> bool:
    """Dibuja el logo en el canvas con esquina inferior izquierda en (x, y).

    Respeta la proporción, cabe en max_h de alto (y en max_w si se indica).
    Devuelve True si lo pintó. Nunca lanza.
    """
    reader = _reader(logo)
    if reader is None:
        return False
    try:
        w, h = reader.getSize()
        alto = max_h
        ancho = alto * (w / h)
        if max_w and ancho > max_w:
            ancho = max_w
            alto = ancho * (h / w)
        canv.drawImage(reader, x, y, width=ancho, height=alto,
                       mask="auto", preserveAspectRatio=True, anchor="sw")
        return True
    except Exception:
        return False
