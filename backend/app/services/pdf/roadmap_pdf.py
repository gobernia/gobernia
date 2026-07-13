"""Deck ejecutivo del Roadmap Estratégico (láminas apaisadas 16:9-ish, A4 landscape).

Estructura de láminas (las que no tienen datos NO se renderizan):
  1. Portada (siempre)
  2. Panorama de retos y oportunidades  (resumen_foda + conclusion_diagnostico)
  3. Tendencias externas que impactan    (resumen_entorno + conclusion_entorno)
  4. Lámina maestra                      (misión/visión/propuesta, objetivos, pilares, estrategias, enablers)
  5. Metas a 3 años                      (metas_3anios)
  6. Una lámina por pilar                (objetivo, estrategias, plan de implementación, KPIs, resultados)
  7. Plan de ejecución                   (pilares × 3 años, con los temas del año)

Todos los campos son opcionales: un roadmap del esquema viejo (o `{}`) produce un PDF válido.
"""

from datetime import date
from io import BytesIO
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    BaseDocTemplate,
    Flowable,
    Frame,
    KeepInFrame,
    NextPageTemplate,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

# Acentos por pilar (mismos que el timeline del frontend).
_PILAR_COLORS = ["#1e3a5f", "#0f766e", "#b45309", "#6d28d9", "#b91c1c", "#334155"]

_NAVY = colors.HexColor("#1e3a5f")
_INK = colors.HexColor("#1f2937")
_MUTED = colors.HexColor("#64748b")
_SOFT = colors.HexColor("#f1f5f9")
_BORDER = colors.HexColor("#e2e8f0")
_WHITE = colors.white

_PAGE = landscape(A4)
_PW, _PH = _PAGE
_MARGIN_X = 1.5 * cm
_MARGIN_Y = 1.2 * cm
_FW = _PW - 2 * _MARGIN_X       # ancho útil de la lámina
_FH = _PH - 2 * _MARGIN_Y       # alto útil de la lámina

_MESES = ("enero", "febrero", "marzo", "abril", "mayo", "junio",
          "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre")

_POR_DEFINIR = "por definir"


# --------------------------------------------------------------------------- helpers de datos

def format_meta_kpi(value) -> str:
    """Formatea la meta/target de un KPI. Vacío o ausente => 'por definir' (nunca 'None')."""
    if value is None:
        return _POR_DEFINIR
    texto = str(value).strip()
    return texto or _POR_DEFINIR


def _s(value) -> str:
    """String seguro: None => ''."""
    if value is None:
        return ""
    return str(value).strip()


def _clip(value, limite: int) -> str:
    """Trunca en frontera de palabra para que el texto no desborde la lámina."""
    texto = _s(value)
    if len(texto) <= limite:
        return texto
    corte = texto[:limite].rsplit(" ", 1)[0].rstrip(" ,;:.")
    return f"{corte or texto[:limite]}…"


def _lista(value, limite_items: int | None = None, limite_texto: int = 160) -> list[str]:
    """Normaliza una lista de strings, descartando vacíos."""
    if not isinstance(value, list):
        return []
    items = [_clip(x, limite_texto) for x in value if _s(x)]
    return items[:limite_items] if limite_items else items


def _dicts(value) -> list[dict]:
    if not isinstance(value, list):
        return []
    return [x for x in value if isinstance(x, dict)]


def _pilares(roadmap: dict) -> list[dict]:
    """Pilares con nombre, ya con su color de acento asignado."""
    out = []
    for i, p in enumerate(_dicts(roadmap.get("pilares"))):
        if not _s(p.get("nombre")):
            continue
        item = dict(p)
        hexa = _PILAR_COLORS[len(out) % len(_PILAR_COLORS)]
        item["_hex"] = hexa
        item["_color"] = colors.HexColor(hexa)
        out.append(item)
    return out


def _milestones(pilar: dict, key: str) -> list[str]:
    mi = pilar.get("milestones")
    if not isinstance(mi, dict):
        return []
    return _lista(mi.get(key), limite_texto=120)


def _fase_titulo(pilar: dict, key: str) -> str:
    fases = pilar.get("fases")
    if not isinstance(fases, dict):
        return ""
    fase = fases.get(key)
    if not isinstance(fase, dict):
        return ""
    return _clip(fase.get("titulo"), 40)


def _anios_labels(roadmap: dict) -> list[str]:
    """['Año 1', 'Año 2', 'Año 3'] o con el año calendario si hay anio_objetivo."""
    base = roadmap.get("anio_objetivo")
    try:
        base = int(base) - 2
    except (TypeError, ValueError):
        return ["Año 1", "Año 2", "Año 3"]
    return [f"Año {i} · {base + i - 1}" for i in (1, 2, 3)]


def _fecha_es() -> str:
    hoy = date.today()
    return f"{hoy.day} de {_MESES[hoy.month - 1]} de {hoy.year}"


# --------------------------------------------------------------------------- estilos

def _styles() -> dict:
    base = getSampleStyleSheet()
    return {
        "titulo": ParagraphStyle("titulo", parent=base["Normal"], fontName="Helvetica-Bold",
                                 fontSize=19, leading=22, textColor=_WHITE),
        "seccion": ParagraphStyle("seccion", parent=base["Normal"], fontName="Helvetica-Bold",
                                  fontSize=11, leading=13, textColor=_NAVY, spaceBefore=2, spaceAfter=4),
        "cuerpo": ParagraphStyle("cuerpo", parent=base["Normal"], fontName="Helvetica",
                                 fontSize=9.5, leading=13.5, textColor=_INK),
        "bullet": ParagraphStyle("bullet", parent=base["Normal"], fontName="Helvetica",
                                 fontSize=9, leading=12.5, textColor=_INK, spaceAfter=3,
                                 leftIndent=9, firstLineIndent=-9),
        "mini": ParagraphStyle("mini", parent=base["Normal"], fontName="Helvetica",
                               fontSize=8, leading=11, textColor=_MUTED),
        "mini_bold": ParagraphStyle("mini_bold", parent=base["Normal"], fontName="Helvetica-Bold",
                                    fontSize=8.5, leading=11.5, textColor=_INK),
        "card_titulo": ParagraphStyle("card_titulo", parent=base["Normal"], fontName="Helvetica-Bold",
                                      fontSize=10, leading=12.5, textColor=_WHITE),
        "destacado": ParagraphStyle("destacado", parent=base["Normal"], fontName="Helvetica-Bold",
                                    fontSize=11, leading=15, textColor=_NAVY),
        "blanco": ParagraphStyle("blanco", parent=base["Normal"], fontName="Helvetica",
                                 fontSize=9, leading=12, textColor=_WHITE),
        "blanco_bold": ParagraphStyle("blanco_bold", parent=base["Normal"], fontName="Helvetica-Bold",
                                      fontSize=9.5, leading=12.5, textColor=_WHITE),
    }


class _Rule(Flowable):
    """Línea horizontal fina."""

    def __init__(self, width: float, color=_BORDER, thickness: float = 0.7):
        super().__init__()
        self.width, self.color, self.thickness = width, color, thickness
        self.height = thickness

    def draw(self):
        self.canv.setStrokeColor(self.color)
        self.canv.setLineWidth(self.thickness)
        self.canv.line(0, 0, self.width, 0)


# --------------------------------------------------------------------------- bloques reutilizables

def _encabezado(titulo: str, st: dict, color=_NAVY, subtitulo: str = "") -> Table:
    """Banda de color a lo ancho de la lámina con el título (y opcionalmente el objetivo)."""
    filas = [[Paragraph(escape(titulo), st["titulo"])]]
    if subtitulo:
        filas.append([Paragraph(escape(subtitulo), st["blanco"])])
    t = Table(filas, colWidths=[_FW])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), color),
        ("LEFTPADDING", (0, 0), (-1, -1), 12),
        ("RIGHTPADDING", (0, 0), (-1, -1), 12),
        ("TOPPADDING", (0, 0), (-1, 0), 10),
        ("BOTTOMPADDING", (0, -1), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 2 if subtitulo else 10),
        ("TOPPADDING", (0, -1), (-1, -1), 0 if subtitulo else 10),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    return t


def _caja(titulo: str, contenido: list, st: dict, ancho: float, color=_NAVY, tint=_SOFT) -> Table:
    """Caja con cabecera de color y contenido debajo."""
    filas = [[Paragraph(escape(titulo), st["card_titulo"])], [contenido]]
    t = Table(filas, colWidths=[ancho])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, 0), color),
        ("BACKGROUND", (0, 1), (0, 1), tint),
        ("BOX", (0, 0), (-1, -1), 0.5, _BORDER),
        ("LEFTPADDING", (0, 0), (-1, -1), 9),
        ("RIGHTPADDING", (0, 0), (-1, -1), 9),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ("VALIGN", (0, 1), (0, 1), "TOP"),
    ]))
    return t


def _franja(etiqueta: str, contenido: list, st: dict, color=_NAVY) -> Table:
    """Franja horizontal: etiqueta a la izquierda (fondo de color) + contenido a la derecha."""
    lbl_w = 4.6 * cm
    t = Table([[Paragraph(escape(etiqueta), st["card_titulo"]), contenido]],
              colWidths=[lbl_w, _FW - lbl_w])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, 0), color),
        ("BACKGROUND", (1, 0), (1, 0), _SOFT),
        ("BOX", (0, 0), (-1, -1), 0.5, _BORDER),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 9),
        ("RIGHTPADDING", (0, 0), (-1, -1), 9),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
    ]))
    return t


def _destacado(texto: str, st: dict, color=_NAVY) -> Table:
    """Barra destacada con una conclusión (acento de color a la izquierda)."""
    t = Table([["", Paragraph(escape(texto), st["destacado"])]], colWidths=[5, _FW - 5])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, 0), color),
        ("BACKGROUND", (1, 0), (1, 0), _SOFT),
        ("LEFTPADDING", (0, 0), (0, 0), 0),
        ("RIGHTPADDING", (0, 0), (0, 0), 0),
        ("LEFTPADDING", (1, 0), (1, 0), 12),
        ("RIGHTPADDING", (1, 0), (1, 0), 12),
        ("TOPPADDING", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    return t


def _bullets(items: list[str], st: dict, estilo: str = "bullet") -> list:
    return [Paragraph(f"•&nbsp;&nbsp;{escape(x)}", st[estilo]) for x in items]


def _prosa(texto: str, st: dict) -> Table:
    """Párrafo largo en una columna de medida legible (no a todo lo ancho de la lámina)."""
    ancho = _FW * 0.72
    t = Table([[Paragraph(escape(texto), st["cuerpo"])]], colWidths=[ancho], hAlign="LEFT")
    t.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    return t


def _columnas(celdas: list[list], anchos: list[float], padding: int = 0) -> Table:
    """Fila de columnas sin fondo (para maquetar bloques lado a lado)."""
    t = Table([celdas], colWidths=anchos)
    t.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), padding),
        ("RIGHTPADDING", (0, 0), (-1, -1), padding),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    return t


# --------------------------------------------------------------------------- láminas

def _lamina(titulo: str, cuerpo: list, st: dict, color=_NAVY, subtitulo: str = "") -> list:
    """Encabezado + cuerpo encogido para que jamás desborde la lámina."""
    hdr = _encabezado(titulo, st, color=color, subtitulo=subtitulo)
    alto_hdr = hdr.wrap(_FW, _FH)[1]
    disponible = max(_FH - alto_hdr - 14, 40)
    return [hdr, Spacer(1, 12), KeepInFrame(_FW, disponible, cuerpo, mode="shrink")]


def _slide_panorama(roadmap: dict, st: dict) -> list:
    foda = _clip(roadmap.get("resumen_foda"), 1400)
    concl = _clip(roadmap.get("conclusion_diagnostico"), 400)
    if not foda and not concl:
        return []
    cuerpo: list = []
    if foda:
        cuerpo.append(Paragraph("Situación actual", st["seccion"]))
        cuerpo.append(_prosa(foda, st))
        cuerpo.append(Spacer(1, 16))
    if concl:
        cuerpo.append(_destacado(concl, st))
    return _lamina("Panorama de retos y oportunidades", cuerpo, st)


def _slide_tendencias(roadmap: dict, st: dict) -> list:
    entorno = _clip(roadmap.get("resumen_entorno"), 1400)
    concl = _clip(roadmap.get("conclusion_entorno"), 400)
    if not entorno and not concl:
        return []
    cuerpo: list = []
    if entorno:
        cuerpo.append(Paragraph("Contexto del entorno", st["seccion"]))
        cuerpo.append(_prosa(entorno, st))
        cuerpo.append(Spacer(1, 16))
    if concl:
        cuerpo.append(_destacado(concl, st, color=colors.HexColor("#0f766e")))
    return _lamina("Tendencias externas que impactan", cuerpo, st, color=colors.HexColor("#0f766e"))


def _card_pilar(pilar: dict, st: dict, ancho: float) -> Table:
    """Tarjeta compacta de un pilar para la lámina maestra."""
    interior: list = []
    desc = _clip(pilar.get("descripcion"), 110)
    if desc:
        interior.append(Paragraph(escape(desc), st["mini"]))
    kpis = _dicts(pilar.get("kpis"))
    if kpis:
        if interior:
            interior.append(Spacer(1, 5))
        for k in kpis[:3]:
            label = _clip(k.get("label"), 34)
            if not label:
                continue
            actual = _s(k.get("actual"))
            meta = format_meta_kpi(k.get("meta"))
            pie = f"{escape(actual)} → {escape(meta)}" if actual else escape(meta)
            interior.append(Paragraph(
                f'{escape(label)}<br/><font color="#64748b">{pie}</font>', st["mini_bold"]))
    if not interior:
        interior.append(Spacer(1, 2))
    return _caja(_clip(pilar.get("nombre"), 44), interior, st, ancho, color=pilar["_color"], tint=_WHITE)


def _slide_maestra(roadmap: dict, pilares: list[dict], st: dict) -> list:
    mision = _clip(roadmap.get("mision"), 320)
    vision = _clip(roadmap.get("vision"), 320)
    propuesta = _clip(roadmap.get("propuesta_valor"), 320)
    objetivos = _lista(roadmap.get("objetivos_estrategicos"), 6, 90)
    enablers = _lista(roadmap.get("key_enablers"), 6, 60)
    estrategias_por_pilar = [(p, _lista(p.get("estrategias"), 4, 90)) for p in pilares]
    hay_estrategias = any(e for _p, e in estrategias_por_pilar)

    if not (mision or vision or propuesta or objetivos or enablers or pilares):
        return []

    cuerpo: list = []

    # Misión / Visión / Propuesta de valor
    cajas = [(t, v) for t, v in (("Misión", mision), ("Visión", vision),
                                 ("Propuesta de valor", propuesta)) if v]
    if cajas:
        gap = 10
        ancho = (_FW - gap * (len(cajas) - 1)) / len(cajas)
        celdas, anchos = [], []
        for i, (titulo, val) in enumerate(cajas):
            celdas.append(_caja(titulo, [Paragraph(escape(val), st["cuerpo"])], st, ancho))
            anchos.append(ancho)
            if i < len(cajas) - 1:
                celdas.append("")
                anchos.append(gap)
        cuerpo.append(_columnas(celdas, anchos))
        cuerpo.append(Spacer(1, 10))

    # Objetivos estratégicos (franja)
    if objetivos:
        mitad = (len(objetivos) + 1) // 2
        cols = [objetivos[:mitad], objetivos[mitad:]]
        cols = [c for c in cols if c]
        ancho_col = (_FW - 4.6 * cm - 18) / len(cols)
        contenido = _columnas([_bullets(c, st) for c in cols], [ancho_col] * len(cols))
        cuerpo.append(_franja("Objetivos estratégicos", [contenido], st))
        cuerpo.append(Spacer(1, 10))

    # Tarjetas de pilares
    if pilares:
        gap = 8
        ancho = (_FW - gap * (len(pilares) - 1)) / len(pilares)
        celdas, anchos = [], []
        for i, p in enumerate(pilares):
            celdas.append(_card_pilar(p, st, ancho))
            anchos.append(ancho)
            if i < len(pilares) - 1:
                celdas.append("")
                anchos.append(gap)
        cuerpo.append(_columnas(celdas, anchos))
        cuerpo.append(Spacer(1, 10))

    # Estrategias clave por pilar (columnas)
    if hay_estrategias:
        gap = 8
        n = len(estrategias_por_pilar)
        ancho = (_FW - gap * (n - 1)) / n
        celdas, anchos = [], []
        for i, (p, ests) in enumerate(estrategias_por_pilar):
            col: list = [Paragraph(
                f'<font color="{p["_hex"]}">{escape(_clip(p.get("nombre"), 40))}</font>', st["mini_bold"])]
            col.extend(_bullets(ests, st, "mini") if ests else [Paragraph("—", st["mini"])])
            celdas.append(col)
            anchos.append(ancho)
            if i < n - 1:
                celdas.append("")
                anchos.append(gap)
        cuerpo.append(Paragraph("Estrategias clave", st["seccion"]))
        cuerpo.append(_Rule(_FW))
        cuerpo.append(Spacer(1, 6))
        cuerpo.append(_columnas(celdas, anchos))
        cuerpo.append(Spacer(1, 10))

    # Key enablers (franja final)
    if enablers:
        texto = "   ·   ".join(escape(e) for e in enablers)
        cuerpo.append(_franja("Key enablers", [Paragraph(texto, st["cuerpo"])], st,
                              color=colors.HexColor("#334155")))

    anio = roadmap.get("anio_objetivo")
    titulo = f"Marco estratégico {anio}" if isinstance(anio, int) else "Marco estratégico"
    return _lamina(titulo, cuerpo, st)


def _slide_metas(roadmap: dict, st: dict) -> list:
    metas = [m for m in _dicts(roadmap.get("metas_3anios")) if _s(m.get("meta"))]
    if not metas:
        return []
    filas = [[Paragraph("Meta", st["mini_bold"]), Paragraph("KPI", st["mini_bold"]),
              Paragraph("Hoy", st["mini_bold"]), Paragraph("Meta a 3 años", st["mini_bold"])]]
    for m in metas[:12]:
        filas.append([
            Paragraph(escape(_clip(m.get("meta"), 90)), st["cuerpo"]),
            Paragraph(escape(_clip(m.get("kpi"), 50)) or "—", st["mini"]),
            Paragraph(escape(_s(m.get("valor_actual"))) or "—", st["cuerpo"]),
            Paragraph(escape(format_meta_kpi(m.get("target"))), st["destacado"]),
        ])
    anchos = [_FW * 0.40, _FW * 0.22, _FW * 0.16, _FW * 0.22]
    t = Table(filas, colWidths=anchos, repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), _SOFT),
        ("LINEBELOW", (0, 0), (-1, -1), 0.5, _BORDER),
        ("BOX", (0, 0), (-1, -1), 0.5, _BORDER),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 9),
        ("RIGHTPADDING", (0, 0), (-1, -1), 9),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
    ]))
    return _lamina("Metas a 3 años", [t], st)


def _slide_pilar(pilar: dict, roadmap: dict, st: dict) -> list:
    color = pilar["_color"]
    estrategias = _lista(pilar.get("estrategias"), 6, 130)
    resultados = _dicts(pilar.get("resultados_esperados"))
    kpis = _dicts(pilar.get("kpis"))
    anios = _anios_labels(roadmap)
    fases = [(anios[i], _fase_titulo(pilar, f"anio{i + 1}"), _milestones(pilar, f"anio{i + 1}"))
             for i in range(3)]
    hay_plan = any(titulo or mls for _a, titulo, mls in fases)

    cuerpo: list = []

    # Estrategias principales + Resultados esperados (dos columnas si hay ambos)
    bloques = []
    if estrategias:
        col = [Paragraph("Estrategias principales", st["seccion"])]
        col.extend(_bullets(estrategias, st))
        bloques.append(col)
    if resultados:
        col = [Paragraph("Resultados esperados", st["seccion"])]
        for r in resultados[:5]:
            titulo = _clip(r.get("titulo"), 60)
            desc = _clip(r.get("descripcion"), 130)
            if not titulo and not desc:
                continue
            txt = f"<b>{escape(titulo)}</b>" if titulo else ""
            if desc:
                txt = f"{txt}<br/>{escape(desc)}" if txt else escape(desc)
            col.append(Paragraph(txt, st["bullet"]))
        bloques.append(col)
    if bloques:
        if len(bloques) == 2:
            gap = 16
            ancho = (_FW - gap) / 2
            cuerpo.append(_columnas([bloques[0], "", bloques[1]], [ancho, gap, ancho]))
        else:
            cuerpo.extend(bloques[0])
        cuerpo.append(Spacer(1, 12))

    # Plan de implementación (3 fases)
    if hay_plan:
        cuerpo.append(Paragraph("Plan de implementación", st["seccion"]))
        cuerpo.append(Spacer(1, 4))
        gap = 8
        ancho = (_FW - gap * 2) / 3
        celdas, anchos = [], []
        for i, (etiqueta, titulo, mls) in enumerate(fases):
            interior: list = []
            if titulo:
                interior.append(Paragraph(escape(titulo), st["mini_bold"]))
                interior.append(Spacer(1, 3))
            interior.extend(_bullets(mls, st, "mini") if mls else [Paragraph("—", st["mini"])])
            celdas.append(_caja(etiqueta, interior, st, ancho, color=color, tint=_SOFT))
            anchos.append(ancho)
            if i < 2:
                celdas.append("")
                anchos.append(gap)
        cuerpo.append(_columnas(celdas, anchos))
        cuerpo.append(Spacer(1, 12))

    # KPIs
    kpi_filas = []
    for k in kpis[:6]:
        label = _clip(k.get("label"), 60)
        if not label:
            continue
        kpi_filas.append([
            Paragraph(escape(label), st["cuerpo"]),
            Paragraph(escape(_s(k.get("actual"))) or "—", st["cuerpo"]),
            Paragraph("→", st["mini"]),
            Paragraph(escape(format_meta_kpi(k.get("meta"))), st["destacado"]),
        ])
    if kpi_filas:
        cuerpo.append(Paragraph("KPIs", st["seccion"]))
        cuerpo.append(Spacer(1, 4))
        anchos = [_FW * 0.46, _FW * 0.18, _FW * 0.06, _FW * 0.30]
        t = Table(kpi_filas, colWidths=anchos)
        t.setStyle(TableStyle([
            ("LINEBELOW", (0, 0), (-1, -1), 0.5, _BORDER),
            ("LINEABOVE", (0, 0), (-1, 0), 0.5, _BORDER),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 9),
            ("RIGHTPADDING", (0, 0), (-1, -1), 9),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ]))
        cuerpo.append(t)

    if not cuerpo:
        cuerpo.append(Paragraph(escape(_clip(pilar.get("descripcion"), 400)) or "—", st["cuerpo"]))

    return _lamina(_clip(pilar.get("nombre"), 70), cuerpo, st, color=color,
                   subtitulo=_clip(pilar.get("objetivo"), 180))


def _slide_ejecucion(roadmap: dict, pilares: list[dict], st: dict) -> list:
    if not pilares:
        return []
    con_datos = any(_milestones(p, f"anio{i}") for p in pilares for i in (1, 2, 3))
    if not con_datos:
        return []

    temas = roadmap.get("temas_por_anio") if isinstance(roadmap.get("temas_por_anio"), dict) else {}
    anios = _anios_labels(roadmap)

    cabecera = [Paragraph("Pilar", st["blanco_bold"])]
    for i, etiqueta in enumerate(anios):
        tema = _clip((temas or {}).get(f"anio{i + 1}"), 40)
        txt = escape(etiqueta)
        if tema:
            txt += f'<br/><font size=8 color="#cbd5e1">{escape(tema)}</font>'
        cabecera.append(Paragraph(txt, st["blanco_bold"]))
    filas = [cabecera]

    estilo = [
        ("BACKGROUND", (0, 0), (-1, 0), _NAVY),
        ("GRID", (0, 0), (-1, -1), 0.5, _BORDER),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
    ]

    for r, p in enumerate(pilares, start=1):
        fila = [Paragraph(f'<font color="#ffffff">{escape(_clip(p.get("nombre"), 40))}</font>',
                          st["mini_bold"])]
        for i in (1, 2, 3):
            mls = _milestones(p, f"anio{i}")
            fila.append(_bullets(mls[:4], st, "mini") if mls else [Paragraph("—", st["mini"])])
        filas.append(fila)
        estilo.append(("BACKGROUND", (0, r), (0, r), p["_color"]))
        if r % 2 == 0:
            estilo.append(("BACKGROUND", (1, r), (-1, r), _SOFT))

    col0 = _FW * 0.22
    resto = (_FW - col0) / 3
    t = Table(filas, colWidths=[col0, resto, resto, resto], repeatRows=1)
    t.setStyle(TableStyle(estilo))
    return _lamina("Plan de ejecución", [t], st)


# --------------------------------------------------------------------------- portada

def _dibuja_portada(canv, doc, roadmap: dict, company_name: str | None) -> None:
    canv.saveState()
    # Fondo navy a sangre.
    canv.setFillColor(_NAVY)
    canv.rect(0, 0, _PW, _PH, stroke=0, fill=1)

    # Hueco reservado para el logo del cliente (arriba a la izquierda). No se dibuja nada.
    logo_h = 1.8 * cm
    logo_top = _PH - _MARGIN_Y - logo_h

    # Regla de acento.
    canv.setFillColor(colors.HexColor("#38bdf8"))
    canv.rect(_MARGIN_X, logo_top - 2.6 * cm, 2.4 * cm, 3, stroke=0, fill=1)

    y = logo_top - 3.9 * cm
    empresa = _clip(company_name, 60)
    if empresa:
        canv.setFillColor(colors.HexColor("#93c5fd"))
        canv.setFont("Helvetica-Bold", 15)
        canv.drawString(_MARGIN_X, y, empresa)
        y -= 1.25 * cm

    anio = roadmap.get("anio_objetivo")
    if isinstance(anio, int):
        titulo, resalte = "Roadmap Estratégico", f"al {anio}"
    else:
        titulo, resalte = "Roadmap Estratégico", "a 3 años"
    canv.setFillColor(_WHITE)
    canv.setFont("Helvetica-Bold", 40)
    canv.drawString(_MARGIN_X, y, titulo)
    y -= 1.5 * cm
    canv.setFillColor(colors.HexColor("#7dd3fc"))
    canv.setFont("Helvetica-Bold", 34)
    canv.drawString(_MARGIN_X, y, resalte)

    # Pie: fecha de generación.
    canv.setFillColor(colors.HexColor("#94a3b8"))
    canv.setFont("Helvetica", 9.5)
    canv.drawString(_MARGIN_X, _MARGIN_Y + 0.2 * cm, f"Generado el {_fecha_es()}")
    canv.restoreState()


def _dibuja_pie(canv, doc, company_name: str | None) -> None:
    canv.saveState()
    canv.setStrokeColor(_BORDER)
    canv.setLineWidth(0.5)
    canv.line(_MARGIN_X, _MARGIN_Y - 0.35 * cm, _PW - _MARGIN_X, _MARGIN_Y - 0.35 * cm)
    canv.setFillColor(_MUTED)
    canv.setFont("Helvetica", 7.5)
    izq = _clip(company_name, 50)
    if izq:
        canv.drawString(_MARGIN_X, _MARGIN_Y - 0.85 * cm, izq)
    canv.drawRightString(_PW - _MARGIN_X, _MARGIN_Y - 0.85 * cm,
                         f"Roadmap Estratégico · {canv.getPageNumber()}")
    canv.restoreState()


# --------------------------------------------------------------------------- entry point

def build_roadmap_pdf(roadmap: dict, company_name: str | None) -> bytes:
    roadmap = roadmap if isinstance(roadmap, dict) else {}
    st = _styles()
    pilares = _pilares(roadmap)

    buf = BytesIO()
    doc = BaseDocTemplate(
        buf, pagesize=_PAGE,
        leftMargin=_MARGIN_X, rightMargin=_MARGIN_X,
        topMargin=_MARGIN_Y, bottomMargin=_MARGIN_Y,
        title=f"Roadmap Estratégico — {company_name or 'Gobernia'}",
        author="Gobernia",
    )
    marco = Frame(_MARGIN_X, _MARGIN_Y, _FW, _FH, id="lamina",
                  leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
    doc.addPageTemplates([
        PageTemplate(id="portada", frames=[marco],
                     onPage=lambda c, d: _dibuja_portada(c, d, roadmap, company_name)),
        PageTemplate(id="lamina", frames=[marco],
                     onPage=lambda c, d: _dibuja_pie(c, d, company_name)),
    ])

    # 1. Portada (todo se dibuja en el canvas; el frame solo fuerza la página).
    story: list = [NextPageTemplate("lamina"), Spacer(1, 1)]

    laminas = [
        _slide_panorama(roadmap, st),
        _slide_tendencias(roadmap, st),
        _slide_maestra(roadmap, pilares, st),
        _slide_metas(roadmap, st),
    ]
    laminas.extend(_slide_pilar(p, roadmap, st) for p in pilares)
    laminas.append(_slide_ejecucion(roadmap, pilares, st))

    for lamina in laminas:
        if not lamina:
            continue  # regla de oro: las láminas sin datos no se renderizan
        story.append(PageBreak())
        story.extend(lamina)

    doc.build(story)
    return buf.getvalue()
