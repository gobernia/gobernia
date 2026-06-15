from io import BytesIO
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer


def build_diagnostico_pdf(content: dict, company_name: str | None) -> bytes:
    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=letter,
        topMargin=2 * cm, bottomMargin=2 * cm, leftMargin=2 * cm, rightMargin=2 * cm,
    )
    base = getSampleStyleSheet()
    h1 = ParagraphStyle("h1", parent=base["Title"], fontSize=20, spaceAfter=6)
    h2 = ParagraphStyle("h2", parent=base["Heading2"], fontSize=14, spaceBefore=14, spaceAfter=6)
    body = ParagraphStyle("body", parent=base["BodyText"], fontSize=10.5, leading=15)
    small = ParagraphStyle("small", parent=base["BodyText"], fontSize=8.5, leading=12, textColor=colors.HexColor("#666666"))

    story = [
        Paragraph(escape(f"Diagnóstico estratégico — {company_name or 'tu empresa'}"), h1),
        Spacer(1, 0.3 * cm),
    ]
    for s in content.get("sections", []):
        story.append(Paragraph(escape(s.get("title", "")), h2))
        for para in (s.get("body", "") or "").split("\n"):
            if para.strip():
                story.append(Paragraph(escape(para.strip()), body))
    sources = content.get("sources", [])
    if sources:
        story.append(Paragraph("Fuentes", h2))
        for src in sources:
            story.append(Paragraph(escape(f"{src.get('title', '')} — {src.get('url', '')}"), small))
    doc.build(story)
    return buf.getvalue()
