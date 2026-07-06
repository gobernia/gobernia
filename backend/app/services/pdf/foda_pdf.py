from io import BytesIO
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle, ListFlowable, ListItem,
)

# (clave, etiqueta, color fuerte, fondo claro) — alineado con la UI.
_QUADS = [
    ("fortalezas", "Fortalezas", "#16a34a", "#f0fdf4"),
    ("oportunidades", "Oportunidades", "#1e3a5f", "#eff6ff"),
    ("debilidades", "Debilidades", "#d97706", "#fffbeb"),
    ("amenazas", "Amenazas", "#dc2626", "#fef2f2"),
]


def build_foda_pdf(foda: dict, metas: list, company_name: str | None) -> bytes:
    foda = foda or {}
    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=letter,
        topMargin=2 * cm, bottomMargin=2 * cm, leftMargin=2 * cm, rightMargin=2 * cm,
    )
    base = getSampleStyleSheet()
    h1 = ParagraphStyle("h1", parent=base["Title"], fontSize=20, spaceAfter=6)
    h2 = ParagraphStyle("h2", parent=base["Heading2"], fontSize=13, spaceBefore=14, spaceAfter=6)
    body = ParagraphStyle("body", parent=base["BodyText"], fontSize=10, leading=14)
    item = ParagraphStyle("item", parent=base["BodyText"], fontSize=9.5, leading=13)

    story = [
        Paragraph(escape(f"Matriz FODA — {company_name or 'tu empresa'}"), h1),
        Spacer(1, 0.2 * cm),
    ]

    sintesis = str(foda.get("sintesis") or "").strip()
    if sintesis:
        story.append(Paragraph(escape(sintesis), body))
        story.append(Spacer(1, 0.4 * cm))

    def _cell(key: str, label: str, strong: str, _bg: str):
        title_style = ParagraphStyle(f"qt_{key}", parent=base["Heading3"], fontSize=12,
                                     textColor=colors.HexColor(strong), spaceAfter=4)
        items = [str(x).strip() for x in (foda.get(key) or []) if str(x).strip()]
        inner = [Paragraph(escape(label.upper()), title_style)]
        if items:
            inner.append(ListFlowable(
                [ListItem(Paragraph(escape(t), item), leftIndent=10) for t in items],
                bulletType="bullet", bulletColor=colors.HexColor(strong), start="•",
            ))
        else:
            inner.append(Paragraph("—", item))
        return inner

    cells = [_cell(*q) for q in _QUADS]
    data = [[cells[0], cells[1]], [cells[2], cells[3]]]
    table = Table(data, colWidths=[8.2 * cm, 8.2 * cm])
    table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 12),
        ("RIGHTPADDING", (0, 0), (-1, -1), 12),
        ("TOPPADDING", (0, 0), (-1, -1), 12),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 14),
        ("BACKGROUND", (0, 0), (0, 0), colors.HexColor(_QUADS[0][3])),
        ("BACKGROUND", (1, 0), (1, 0), colors.HexColor(_QUADS[1][3])),
        ("BACKGROUND", (0, 1), (0, 1), colors.HexColor(_QUADS[2][3])),
        ("BACKGROUND", (1, 1), (1, 1), colors.HexColor(_QUADS[3][3])),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#e5e7eb")),
        ("INNERGRID", (0, 0), (-1, -1), 6, colors.white),
        ("LINEBEFORE", (0, 0), (-1, -1), 0, colors.white),
    ]))
    story.append(table)

    # El FODA es ANÁLISIS: no incluye prioridades ni recomendaciones (esas viven en Metas y el Plan).
    doc.build(story)
    return buf.getvalue()
