from io import BytesIO
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer


def build_roadmap_pdf(roadmap: dict, company_name: str | None) -> bytes:
    roadmap = roadmap or {}
    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=letter,
                            topMargin=2 * cm, bottomMargin=2 * cm, leftMargin=2 * cm, rightMargin=2 * cm)
    base = getSampleStyleSheet()
    h1 = ParagraphStyle("h1", parent=base["Title"], fontSize=20, spaceAfter=6)
    h2 = ParagraphStyle("h2", parent=base["Heading2"], fontSize=13, spaceBefore=14, spaceAfter=4)
    h3 = ParagraphStyle("h3", parent=base["Heading3"], fontSize=11, spaceBefore=8, spaceAfter=2,
                        textColor=colors.HexColor("#1e3a5f"))
    body = ParagraphStyle("body", parent=base["BodyText"], fontSize=10.5, leading=15)
    item = ParagraphStyle("item", parent=base["BodyText"], fontSize=10, leading=14, spaceAfter=2)
    label = ParagraphStyle("label", parent=base["BodyText"], fontSize=8, leading=11,
                           textColor=colors.HexColor("#888888"), spaceAfter=1)

    story = [Paragraph(escape(f"Roadmap estratégico — {company_name or 'tu empresa'}"), h1), Spacer(1, 0.2 * cm)]

    def _txt(title, val):
        if str(val or "").strip():
            story.append(Paragraph(title, h3))
            story.append(Paragraph(escape(str(val).strip()), body))

    _txt("Visión", roadmap.get("vision"))
    _txt("Misión", roadmap.get("mision"))
    _txt("Propuesta de valor", roadmap.get("propuesta_valor"))

    metas = roadmap.get("metas_3anios") or []
    if metas:
        story.append(Paragraph("Metas a 3 años", h2))
        for m in metas:
            if not isinstance(m, dict) or not str(m.get("meta") or "").strip():
                continue
            va = str(m.get("valor_actual") or "").strip()
            tg = str(m.get("target") or "").strip()
            partes = []
            if va:
                partes.append(f"hoy: {escape(va)}")
            if tg:
                partes.append(f"meta: {escape(tg)}")
            anexo = f' <font size=8 color="#888888">({" · ".join(partes)})</font>' if partes else ""
            story.append(Paragraph(f'● {escape(str(m["meta"]).strip())}{anexo}', item))

    _txt("Resumen FODA", roadmap.get("resumen_foda"))
    _txt("Resumen del entorno", roadmap.get("resumen_entorno"))

    pilares = roadmap.get("pilares") or []
    if pilares:
        story.append(Paragraph("Pilares estratégicos", h2))
        for p in pilares:
            if not isinstance(p, dict) or not str(p.get("nombre") or "").strip():
                continue
            story.append(Paragraph(escape(str(p["nombre"]).strip()), h3))
            if str(p.get("descripcion") or "").strip():
                story.append(Paragraph(escape(str(p["descripcion"]).strip()), body))
            mi = p.get("milestones") or {}
            for anio, key in (("Año 1", "anio1"), ("Año 2", "anio2"), ("Año 3", "anio3")):
                vals = mi.get(key)
                mls = [str(x).strip() for x in vals if str(x).strip()] if isinstance(vals, list) else []
                if mls:
                    story.append(Paragraph(anio.upper(), label))
                    for it in mls:
                        story.append(Paragraph(f"● {escape(it)}", item))

    doc.build(story)
    return buf.getvalue()
