"""Genera el PDF de la Orden del Día (Bloque B5) con reportlab. Determinista, sin DB."""
from datetime import date
from io import BytesIO
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

_GREY = colors.HexColor("#6b7280")
_MUTED = colors.HexColor("#9ca3af")


def build_orden_pdf(data: dict, company_name: str | None) -> bytes:
    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=letter,
        topMargin=2 * cm, bottomMargin=2 * cm, leftMargin=2 * cm, rightMargin=2 * cm,
    )
    base = getSampleStyleSheet()
    s_company = ParagraphStyle("company", parent=base["Title"], fontSize=16, spaceAfter=2, alignment=0)
    s_sub = ParagraphStyle("sub", parent=base["Normal"], fontSize=11, textColor=_GREY, spaceAfter=14)
    s_section = ParagraphStyle("section", parent=base["Heading2"], fontSize=12, spaceBefore=12, spaceAfter=6)
    s_body = base["Normal"]
    s_muted = ParagraphStyle("muted", parent=base["Normal"], fontSize=9, textColor=_MUTED)

    covered = set(data.get("covered_keys") or [])
    story = []

    # escape() en TODO el contenido de usuario: reportlab parsea markup XML, un '&' lo rompe.
    # Separadores ASCII ('-') para evitar caracteres fuera de la fuente base.
    story.append(Paragraph(escape(company_name or "Plan estratégico de 12 meses"), s_company))
    story.append(Paragraph(
        escape(f"Orden del día - {data['period_label']} - Sesión {data['month_index']}"), s_sub))

    def _theme_lines(title, themes):
        if not themes:
            return
        story.append(Paragraph(f"<b>{title}</b>", s_body))  # title es literal nuestro, seguro
        for t in themes:
            suffix = " (cubierto)" if t.key in covered else ""
            story.append(Paragraph(escape(f"- {t.label}{suffix}"), s_body))
        story.append(Spacer(1, 6))

    perms = data.get("permanent_themes") or []
    cobs = data.get("coverage_themes") or []
    if perms or cobs:
        story.append(Paragraph("Temas del Consejo", s_section))
        _theme_lines("Permanentes", perms)
        _theme_lines("Cobertura este mes", cobs)

    objs = data.get("objectives") or []
    if objs:
        story.append(Paragraph("Objetivos del mes", s_section))
        for o in objs:
            story.append(Paragraph(escape(o.title), s_body))
            if o.kpi_refs:
                story.append(Paragraph(escape(", ".join(o.kpi_refs)), s_muted))

    story.append(Spacer(1, 18))
    story.append(Paragraph(escape(f"Generado por Gobernia - {date.today().isoformat()}"), s_muted))

    doc.build(story)
    return buf.getvalue()
