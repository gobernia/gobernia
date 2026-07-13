"""Los 4 PDFs se generan con logo, sin logo y con bytes corruptos — nunca lanzan."""
from io import BytesIO

import pytest
from PIL import Image

from app.services.pdf.diagnostico_pdf import build_diagnostico_pdf
from app.services.pdf.foda_pdf import build_foda_pdf
from app.services.pdf.logo import draw_logo, logo_flowable
from app.services.pdf.orden_del_dia_pdf import build_orden_pdf
from app.services.pdf.roadmap_pdf import build_roadmap_pdf

CORRUPTO = b"noesunpng"


def _png_1x1() -> bytes:
    buf = BytesIO()
    Image.new("RGBA", (1, 1), (255, 0, 0, 255)).save(buf, format="PNG")
    return buf.getvalue()


def _orden_data():
    return {
        "month_index": 1, "period_year": 2026, "period_month": 3,
        "period_label": "marzo 2026",
        "permanent_themes": [], "coverage_themes": [], "covered_keys": [],
        "objectives": [],
    }


def _roadmap():
    return {
        "anio_objetivo": 2029,
        "vision": "Ser el líder",
        "pilares": [{"nombre": "Comercial", "objetivo": "Crecer",
                     "estrategias": ["Abrir canal"], "kpis": [{"label": "Ventas", "meta": "10M"}],
                     "milestones": {"anio1": ["Piloto"]}}],
    }


def _foda():
    return {"sintesis": "Vamos bien", "fortalezas": ["Equipo"], "debilidades": ["Caja"],
            "oportunidades": ["Mercado"], "amenazas": ["Competencia"]}


def _diagnostico():
    return {
        "fortalezas_debilidades": {"finanzas": [{"tipo": "fortaleza", "texto": "Margen sano"}]},
        "riesgos": [{"riesgo": "Concentración de clientes", "severidad": "alta"}],
        "sections": [{"title": "Mercado", "body": "Crece 5%."}],
        "sources": [{"title": "INEGI", "url": "https://inegi.org.mx"}],
    }


BUILDERS = [
    ("roadmap", lambda logo: build_roadmap_pdf(_roadmap(), "ACME", logo)),
    ("diagnostico", lambda logo: build_diagnostico_pdf(_diagnostico(), "ACME", logo)),
    ("foda", lambda logo: build_foda_pdf(_foda(), [], "ACME", logo)),
    ("orden", lambda logo: build_orden_pdf(_orden_data(), "ACME", logo)),
]


@pytest.mark.parametrize("nombre,build", BUILDERS, ids=[b[0] for b in BUILDERS])
def test_pdf_sin_logo(nombre, build):
    assert build(None).startswith(b"%PDF")


@pytest.mark.parametrize("nombre,build", BUILDERS, ids=[b[0] for b in BUILDERS])
def test_pdf_con_logo_real(nombre, build):
    assert build(_png_1x1()).startswith(b"%PDF")


@pytest.mark.parametrize("nombre,build", BUILDERS, ids=[b[0] for b in BUILDERS])
def test_pdf_con_logo_corrupto_no_lanza(nombre, build):
    assert build(CORRUPTO).startswith(b"%PDF")


def test_firmas_retrocompatibles_sin_el_parametro_logo():
    """Las llamadas viejas (sin `logo`) siguen funcionando."""
    assert build_roadmap_pdf(_roadmap(), "ACME").startswith(b"%PDF")
    assert build_diagnostico_pdf(_diagnostico(), "ACME").startswith(b"%PDF")
    assert build_foda_pdf(_foda(), [], "ACME").startswith(b"%PDF")
    assert build_orden_pdf(_orden_data(), "ACME").startswith(b"%PDF")


def test_logo_flowable_devuelve_none_si_no_hay_o_esta_corrupto():
    assert logo_flowable(None, 1.2) is None
    assert logo_flowable(b"", 1.2) is None
    assert logo_flowable(CORRUPTO, 1.2) is None


def test_logo_flowable_respeta_proporcion():
    buf = BytesIO()
    Image.new("RGBA", (200, 100), (0, 0, 0, 255)).save(buf, format="PNG")
    img = logo_flowable(buf.getvalue(), height_cm=1.0)
    assert img is not None
    assert round(img.drawWidth / img.drawHeight, 2) == 2.0


def test_draw_logo_devuelve_false_sin_lanzar():
    from reportlab.pdfgen.canvas import Canvas
    canv = Canvas(BytesIO())
    assert draw_logo(canv, None, 0, 0, 30) is False
    assert draw_logo(canv, CORRUPTO, 0, 0, 30) is False
    assert draw_logo(canv, _png_1x1(), 0, 0, 30) is True
