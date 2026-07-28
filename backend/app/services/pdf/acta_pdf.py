"""Genera el ACTA de la sesión de Consejo como PDF de 5 apartados con reportlab.

Determinista, sin DB ni IA. Recibe el dict de `OrdenCadenaOut` (usa `.model_dump()`)
y arma los apartados: Datos de la sesión, Orden del día, Análisis por punto,
Acuerdos del Consejo y Resumen estratégico. Imita el patrón de `orden_del_dia_pdf`.
"""
from io import BytesIO
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

from app.services.pdf.logo import logo_flowable

_GREY = colors.HexColor("#6b7280")
_MUTED = colors.HexColor("#9ca3af")

_CERRADOS = {"completado", "cerrado"}


def _kpi_line(kpi: dict) -> str:
    """'label: actual → meta' con separador ASCII y texto escapado."""
    label = str(kpi.get("label") or "").strip()
    actual = str(kpi.get("actual") or "").strip() or "-"
    meta = str(kpi.get("meta") or "").strip() or "por definir"
    return escape(f"{label}: {actual} -> {meta}")


def build_acta_pdf(cadena: dict, company_name: str | None, periodo_label: str,
                   fecha_iso: str, logo: bytes | None = None) -> bytes:
    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=letter,
        topMargin=2 * cm, bottomMargin=2 * cm, leftMargin=2 * cm, rightMargin=2 * cm,
    )
    base = getSampleStyleSheet()
    s_company = ParagraphStyle("company", parent=base["Title"], fontSize=16, spaceAfter=2, alignment=0)
    s_sub = ParagraphStyle("sub", parent=base["Normal"], fontSize=11, textColor=_GREY, spaceAfter=14)
    s_section = ParagraphStyle("section", parent=base["Heading2"], fontSize=13, spaceBefore=16, spaceAfter=8)
    s_point = ParagraphStyle("point", parent=base["Heading3"], fontSize=11, spaceBefore=10, spaceAfter=4)
    s_body = base["Normal"]
    s_muted = ParagraphStyle("muted", parent=base["Normal"], fontSize=9, textColor=_MUTED)

    puntos = cadena.get("puntos") or []
    story = []

    # escape() en TODO el contenido de usuario: reportlab parsea markup XML.
    # Separadores ASCII ('->', '-') para no salir de la fuente base.
    marca = logo_flowable(logo, height_cm=1.2)
    if marca is not None:
        story.append(marca)
        story.append(Spacer(1, 0.4 * cm))

    # ── Apartado 1 · Datos de la sesión ──────────────────────────────────────
    story.append(Paragraph(escape(company_name or "Consejo"), s_company))
    story.append(Paragraph("Acta de la sesión de Consejo", s_sub))
    story.append(Paragraph("1. Datos de la sesión", s_section))
    story.append(Paragraph(escape(f"Empresa: {company_name or 'Sin nombre'}"), s_body))
    story.append(Paragraph(escape(f"Sesión de Consejo - {periodo_label}"), s_body))
    story.append(Paragraph(escape(f"Fecha: {fecha_iso}"), s_body))
    story.append(Paragraph("Tipo: Ordinaria", s_body))

    # ── Apartado 2 · Orden del día ───────────────────────────────────────────
    story.append(Paragraph("2. Orden del día", s_section))
    if puntos:
        for i, p in enumerate(puntos, start=1):
            nombre = str(p.get("nombre") or "").strip() or f"Prioridad {i}"
            story.append(Paragraph(escape(f"{i}. {nombre}"), s_body))
    else:
        story.append(Paragraph("Sin puntos en la orden del día.", s_muted))

    # ── Apartado 3 · Análisis por punto ──────────────────────────────────────
    story.append(Paragraph("3. Análisis por punto", s_section))
    if puntos:
        for i, p in enumerate(puntos, start=1):
            nombre = str(p.get("nombre") or "").strip() or f"Prioridad {i}"
            a = p.get("analisis") or {}
            esperaba = a.get("que_se_esperaba") or {}
            ocurrio = a.get("que_ocurrio") or {}
            evidencia = a.get("evidencia") or {}
            desviacion = a.get("desviacion") or {}

            story.append(Paragraph(escape(f"Punto {i} · {nombre}"), s_point))

            meta = str(esperaba.get("meta") or "").strip() or "por definir"
            tareas_planeadas = esperaba.get("tareas_planeadas") or 0
            story.append(Paragraph(
                escape(f"Qué se esperaba: {meta} - {tareas_planeadas} tareas planeadas"), s_body))

            hechas = ocurrio.get("hechas") or 0
            en_proceso = ocurrio.get("en_proceso") or 0
            pendientes = ocurrio.get("pendientes") or 0
            story.append(Paragraph(
                escape(f"Qué ocurrió: {hechas} hechas - {en_proceso} en proceso - "
                       f"{pendientes} pendientes"), s_body))
            for kpi in (ocurrio.get("kpis") or []):
                if str(kpi.get("label") or "").strip():
                    story.append(Paragraph(_kpi_line(kpi), s_muted))

            docs_subidos = evidencia.get("documentos_subidos") or 0
            story.append(Paragraph(escape(f"Evidencia: {docs_subidos} documentos subidos"), s_body))

            vencidas = desviacion.get("tareas_vencidas") or 0
            sin_dato = desviacion.get("kpis_sin_dato") or 0
            story.append(Paragraph(
                escape(f"Desviación: {vencidas} tareas vencidas - {sin_dato} indicadores sin dato"),
                s_body))

            explicacion = a.get("explicacion")
            if explicacion is None or not str(explicacion).strip():
                explicacion = "Se documenta durante la sesión."
            story.append(Paragraph(
                escape(f"Explicación de la administración: {explicacion}"), s_body))

            decision = str(a.get("decision_sugerida") or "").strip() or "Por definir."
            story.append(Paragraph(escape(f"Qué decide el Consejo: {decision}"), s_body))
            story.append(Spacer(1, 6))
    else:
        story.append(Paragraph("Sin puntos que analizar.", s_muted))

    # ── Apartado 4 · Acuerdos del Consejo ────────────────────────────────────
    story.append(Paragraph("4. Acuerdos del Consejo", s_section))
    algun_acuerdo = False
    for i, p in enumerate(puntos, start=1):
        acuerdos = p.get("acuerdos") or []
        if not acuerdos:
            continue
        algun_acuerdo = True
        nombre = str(p.get("nombre") or "").strip() or f"Prioridad {i}"
        story.append(Paragraph(escape(f"Punto {i} · {nombre}"), s_point))
        for ac in acuerdos:
            descripcion = str(ac.get("descripcion") or "").strip()
            responsable = str(ac.get("responsable") or "").strip() or "sin responsable"
            fecha = str(ac.get("fecha_compromiso") or "").strip() or "sin fecha"
            status = str(ac.get("status") or "").strip() or "abierto"
            story.append(Paragraph(
                escape(f"- {descripcion} — {responsable} · {fecha} · {status}"), s_body))
    if not algun_acuerdo:
        story.append(Paragraph("Sin acuerdos registrados aún.", s_muted))

    # ── Apartado 5 · Resumen estratégico (determinista, sin IA) ──────────────
    story.append(Paragraph("5. Resumen estratégico", s_section))
    total = len(puntos)
    avanzan = sum(
        1 for p in puntos
        if str((p.get("analisis") or {}).get("decision_sugerida") or "").startswith("Mantener")
    )
    con_desviacion = total - avanzan
    acuerdos_abiertos = sum(
        1 for p in puntos for ac in (p.get("acuerdos") or [])
        if str(ac.get("status") or "").lower() not in _CERRADOS
    )
    docs_solicitados = sum(len(p.get("documentos_solicitados") or []) for p in puntos)
    resumen = (
        f"En seguimiento {total} prioridades: {avanzan} avanzan según lo previsto, "
        f"{con_desviacion} requieren atención por desviación. "
        f"{acuerdos_abiertos} acuerdos abiertos. "
        f"{docs_solicitados} documentos solicitados para esta sesión."
    )
    story.append(Paragraph(escape(resumen), s_body))

    # ── Pie ──────────────────────────────────────────────────────────────────
    story.append(Spacer(1, 18))
    story.append(Paragraph(escape(f"Generado por Gobernia — {fecha_iso}"), s_muted))

    doc.build(story)
    return buf.getvalue()
