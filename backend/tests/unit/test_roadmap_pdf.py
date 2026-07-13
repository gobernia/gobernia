import re

import pytest
from reportlab import rl_config

from app.services.pdf.roadmap_pdf import build_roadmap_pdf, format_meta_kpi


def _texto_dibujado(pdf: bytes) -> str:
    """Texto que el PDF realmente pinta: los literales `(...)` de los content streams.

    Requiere haber desactivado la compresión de página (rl_config.pageCompression = 0).
    Evita falsos positivos con tokens estructurales del PDF como `/PageMode /UseNone`.
    """
    literales = re.findall(rb"\((?:[^()\\]|\\.)*\)", pdf)
    return " ".join(x[1:-1].decode("latin-1") for x in literales)

# --- Roadmap con TODOS los campos del nuevo esquema (deck de 10 láminas) ---
ROADMAP_COMPLETO = {
    "anio_objetivo": 2029,
    "vision": "Ser la empresa de medios más confiable de la región.",
    "mision": "Crear valor sostenible para clientes, equipo y accionistas.",
    "propuesta_valor": "Calidad, cercanía y resultados medibles.",
    "objetivos_estrategicos": [
        "Duplicar la facturación anual",
        "Profesionalizar el gobierno corporativo",
        "Consolidar la operación en tres mercados",
    ],
    "key_enablers": ["Talento", "Tecnología", "Capital de trabajo"],
    "temas_por_anio": {"anio1": "Ordenar la casa", "anio2": "Escalar", "anio3": "Consolidar"},
    "conclusion_diagnostico": "La empresa tiene base sólida pero procesos informales.",
    "conclusion_entorno": "El mercado crece pero la competencia se profesionaliza rápido.",
    "metas_3anios": [
        {"meta": "Mejorar margen", "kpi": "Margen neto", "valor_actual": "6%", "target": "12%"},
        {"meta": "Reducir rotación", "kpi": "Rotación", "valor_actual": "30%", "target": ""},
    ],
    "resumen_foda": "Marca fuerte, procesos débiles, oportunidad de expansión.",
    "resumen_entorno": "Mercado en crecimiento con presión de precios.",
    "pilares": [
        {
            "nombre": "Excelencia operacional",
            "descripcion": "Procesos claros y medibles.",
            "objetivo": "Reducir 30% el costo de operación en 3 años.",
            "estrategias": ["Mapear y estandarizar procesos", "Automatizar tareas repetitivas"],
            "kpis": [
                {"label": "Costo operativo", "actual": "100", "meta": "70"},
                {"label": "NPS interno", "actual": "40", "meta": ""},
            ],
            "resultados_esperados": [
                {"titulo": "Operación predecible", "descripcion": "Menos retrabajo y errores."},
            ],
            "milestones": {
                "anio1": ["Mapear procesos críticos", "Definir dueños de proceso"],
                "anio2": ["Certificar ISO 9001"],
                "anio3": ["Automatizar 50% de tareas"],
            },
            "fases": {
                "anio1": {"titulo": "Diagnóstico y orden"},
                "anio2": {"titulo": "Estandarización"},
                "anio3": {"titulo": "Automatización"},
            },
        },
        {
            "nombre": "Crecimiento comercial",
            "descripcion": "Nuevos mercados y clientes.",
            "objetivo": "Duplicar la cartera de clientes.",
            "estrategias": ["Abrir canal digital", "Alianzas estratégicas"],
            "kpis": [{"label": "Clientes activos", "actual": "120", "meta": "240"}],
            "resultados_esperados": [{"titulo": "Cartera diversificada", "descripcion": "Menor dependencia."}],
            "milestones": {"anio1": ["Definir ICP"], "anio2": ["Abrir mercado 2"], "anio3": ["Abrir mercado 3"]},
            "fases": {"anio1": {"titulo": "Foco"}, "anio2": {"titulo": "Expansión"}, "anio3": {"titulo": "Escala"}},
        },
    ],
}

# --- Roadmap del esquema VIEJO (sin ninguno de los campos nuevos) ---
ROADMAP_VIEJO = {
    "vision": "Ser referente",
    "mision": "Crear valor",
    "propuesta_valor": "Calidad y cercanía",
    "metas_3anios": [{"meta": "Mejorar margen", "kpi": "Margen", "valor_actual": "6%", "target": "12%"}],
    "resumen_foda": "Sólida.",
    "resumen_entorno": "Mercado en crecimiento.",
    "pilares": [
        {
            "nombre": "Excelencia operacional",
            "descripcion": "Procesos.",
            "milestones": {"anio1": ["Mapear procesos"], "anio2": ["Certificar"], "anio3": ["Automatizar 50%"]},
        }
    ],
}


def test_pdf_roadmap_completo_es_valido():
    pdf = build_roadmap_pdf(ROADMAP_COMPLETO, "Keting Media")
    assert pdf[:5] == b"%PDF-"
    assert len(pdf) > 1000


def test_pdf_roadmap_vacio_no_truena():
    pdf = build_roadmap_pdf({}, None)
    assert pdf[:5] == b"%PDF-"


def test_pdf_roadmap_none_no_truena():
    assert build_roadmap_pdf(None, None)[:5] == b"%PDF-"  # type: ignore[arg-type]


def test_pdf_roadmap_esquema_viejo_es_valido():
    """Un roadmap sin ninguno de los campos nuevos sigue produciendo un PDF correcto."""
    pdf = build_roadmap_pdf(ROADMAP_VIEJO, "Empresa Vieja")
    assert pdf[:5] == b"%PDF-"
    assert len(pdf) > 1000


def test_pdf_roadmap_solo_pilares_sin_texto():
    """Roadmap mínimo: solo pilares con nombre. No debe truenar."""
    pdf = build_roadmap_pdf({"pilares": [{"nombre": "Pilar único"}]}, None)
    assert pdf[:5] == b"%PDF-"


def test_pdf_roadmap_muchos_pilares_no_truena():
    """Más de 5 pilares: el ancho de las tarjetas se ajusta, no desborda."""
    pilares = [
        {"nombre": f"Pilar {i}", "descripcion": "Desc.", "estrategias": [f"Estrategia {i}"],
         "milestones": {"anio1": [f"Hito {i}"]}}
        for i in range(1, 8)
    ]
    pdf = build_roadmap_pdf({"pilares": pilares}, "Muchos Pilares SA")
    assert pdf[:5] == b"%PDF-"


@pytest.mark.parametrize("valor", [None, "", "   "])
def test_format_meta_kpi_vacia_es_por_definir(valor):
    assert format_meta_kpi(valor) == "por definir"


@pytest.mark.parametrize("valor,esperado", [("12%", "12%"), (0, "0"), (240, "240"), ("  70 ", "70")])
def test_format_meta_kpi_con_valor(valor, esperado):
    assert format_meta_kpi(valor) == esperado


def test_pdf_con_meta_vacia_no_escribe_none(monkeypatch):
    """Con `meta`/`target` vacíos el PDF dice 'por definir', nunca 'None'."""
    monkeypatch.setattr(rl_config, "pageCompression", 0)
    roadmap = {
        "metas_3anios": [{"meta": "Mejorar margen", "valor_actual": None, "target": ""}],
        "pilares": [
            {
                "nombre": "Excelencia operacional",
                "objetivo": "Ordenar la operación",
                "kpis": [{"label": "Costo operativo", "actual": None, "meta": None}],
                "milestones": {"anio1": ["Mapear procesos"]},
            }
        ],
    }
    pdf = build_roadmap_pdf(roadmap, "Test Company")
    assert pdf[:5] == b"%PDF-"

    texto = _texto_dibujado(pdf)
    assert "None" not in texto
    assert "por definir" in texto
