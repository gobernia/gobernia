from io import BytesIO
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

from app.services.pdf.logo import logo_flowable

_SEV_COLOR = {"alta": "#dc2626", "media": "#d97706", "baja": "#6b7280"}


def _split_fd(content: dict):
    """Aplana content['fortalezas_debilidades'] a (fortalezas, debilidades), cada una lista de
    (texto, area). Debilidad y parcial cuentan como debilidad."""
    fort, debil = [], []
    for area, items in (content.get("fortalezas_debilidades") or {}).items():
        for h in (items or []):
            if not isinstance(h, dict):
                continue
            tipo = str(h.get("tipo") or "").lower()
            texto = str(h.get("texto") or "").strip()
            if not texto:
                continue
            if tipo == "fortaleza":
                fort.append((texto, str(area)))
            elif tipo in ("debilidad", "parcial"):
                debil.append((texto, str(area)))
    return fort, debil


def build_diagnostico_pdf(content: dict, company_name: str | None,
                          logo: bytes | None = None) -> bytes:
    content = content or {}
    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=letter,
        topMargin=2 * cm, bottomMargin=2 * cm, leftMargin=2 * cm, rightMargin=2 * cm,
    )
    base = getSampleStyleSheet()
    h1 = ParagraphStyle("h1", parent=base["Title"], fontSize=20, spaceAfter=6)
    h2 = ParagraphStyle("h2", parent=base["Heading2"], fontSize=14, spaceBefore=14, spaceAfter=6)
    h3 = ParagraphStyle("h3", parent=base["Heading3"], fontSize=11, spaceBefore=8, spaceAfter=3)
    body = ParagraphStyle("body", parent=base["BodyText"], fontSize=10.5, leading=15)
    item = ParagraphStyle("item", parent=base["BodyText"], fontSize=10, leading=14, spaceAfter=3)
    small = ParagraphStyle("small", parent=base["BodyText"], fontSize=8.5, leading=12,
                           textColor=colors.HexColor("#666666"))

    def _bullet(texto: str, area: str, hexcolor: str):
        tag = f' <font size=7 color="#999999">· {escape(area.upper())}</font>' if area else ""
        return Paragraph(f'<font color="{hexcolor}">●</font> {escape(texto)}{tag}', item)

    story = []
    marca = logo_flowable(logo, height_cm=1.2)
    if marca is not None:
        story.append(marca)
        story.append(Spacer(1, 0.4 * cm))
    story.append(Paragraph(escape(f"Diagnóstico estratégico — {company_name or 'tu empresa'}"), h1))
    story.append(Spacer(1, 0.3 * cm))

    # 1) Interno destacado: Fortalezas → Debilidades → Riesgos
    fort, debil = _split_fd(content)
    if fort:
        story.append(Paragraph("Fortalezas internas", h2))
        story.extend(_bullet(t, a, "#16a34a") for t, a in fort)
    if debil:
        story.append(Paragraph("Debilidades internas", h2))
        story.extend(_bullet(t, a, "#dc2626") for t, a in debil)

    riesgos = content.get("riesgos") or []
    if riesgos:
        story.append(Paragraph("Riesgos", h2))
        for r in riesgos:
            if not isinstance(r, dict):
                continue
            texto = str(r.get("riesgo") or "").strip()
            sev = str(r.get("severidad") or "media").lower()
            if not texto:
                continue
            hexc = _SEV_COLOR.get(sev, "#d97706")
            story.append(Paragraph(
                f'<font color="{hexc}">●</font> {escape(texto)} '
                f'<font size=7 color="#999999">({escape(sev.capitalize())})</font>', item))

    # 2) Contexto de mercado (investigación web)
    secciones = [s for s in (content.get("sections") or []) if (s.get("body") or "").strip()]
    if secciones:
        story.append(Paragraph("Contexto de mercado", h2))
        for s in secciones:
            story.append(Paragraph(escape(s.get("title", "")), h3))
            for para in (s.get("body", "") or "").split("\n"):
                if para.strip():
                    story.append(Paragraph(escape(para.strip()), body))

    # 3) Fuentes
    sources = content.get("sources") or []
    if sources:
        story.append(Paragraph("Fuentes", h2))
        for src in sources:
            story.append(Paragraph(escape(f"{src.get('title', '')} — {src.get('url', '')}"), small))

    doc.build(story)
    return buf.getvalue()
