"""PDF de un «Avance contado a Todd»: lo que el dueño o un responsable le contó a Todd que hicieron
en una tarea, cuando no tenía un documento para subir. Queda como evidencia de la tarea (el Auditor
lo lee igual que cualquier documento) y se puede descargar. Determinista, sin DB."""
from datetime import datetime
from io import BytesIO
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

_GREY = colors.HexColor("#6b7280")
_MESES = ("enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre",
          "octubre", "noviembre", "diciembre")

CAMPOS = (("que_se_hizo", "Qué se hizo"), ("cuando", "Cuándo"), ("quien", "Quién participó"),
          ("resultado", "Resultado"))


def fecha_larga(d: datetime) -> str:
    return f"{d.day} de {_MESES[d.month - 1]} de {d.year}"


def build_avance_pdf(tarea: str, contado_por: str, cuando: datetime, datos: dict) -> bytes:
    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=letter, topMargin=2 * cm, bottomMargin=2 * cm,
                            leftMargin=2 * cm, rightMargin=2 * cm,
                            title="Avance contado a Todd", author="Gobernia")
    base = getSampleStyleSheet()
    s_titulo = ParagraphStyle("titulo", parent=base["Title"], fontSize=16, alignment=0, spaceAfter=4)
    s_sub = ParagraphStyle("sub", parent=base["Normal"], fontSize=10, textColor=_GREY, spaceAfter=14)
    s_campo = ParagraphStyle("campo", parent=base["Heading3"], fontSize=11, spaceBefore=8, spaceAfter=3)
    s_texto = ParagraphStyle("texto", parent=base["Normal"], fontSize=10.5, leading=15)
    s_nota = ParagraphStyle("nota", parent=base["Normal"], fontSize=8.5, textColor=_GREY, spaceBefore=18)

    # escape() en TODO lo que escribió una persona: reportlab interpreta marcas tipo XML.
    story = [
        Paragraph("Avance contado a Todd", s_titulo),
        Paragraph(escape(f"Tarea: {tarea}"), s_texto),
        Paragraph(escape(f"Lo contó {contado_por} el {fecha_larga(cuando)}"), s_sub),
    ]
    for clave, etiqueta in CAMPOS:
        valor = str(datos.get(clave) or "").strip()
        if valor:
            story += [Paragraph(etiqueta, s_campo), Paragraph(escape(valor).replace("\n", "<br/>"), s_texto)]
    story += [Spacer(1, 6), Paragraph(
        "Constancia sin documento de respaldo: es lo que la persona le contó a Todd en el chat de "
        "Gobernia porque no tenía un documento para subir.", s_nota)]
    doc.build(story)
    return buf.getvalue()
