from app.services.pdf.roadmap_pdf import build_roadmap_pdf


def test_pdf_roadmap_completo_es_valido():
    roadmap = {
        "vision": "Ser referente", "mision": "Crear valor", "propuesta_valor": "Calidad y cercanía",
        "metas_3anios": [{"meta": "Mejorar margen", "kpi": "Margen", "valor_actual": "6%", "target": "12%"}],
        "resumen_foda": "Sólida.", "resumen_entorno": "Mercado en crecimiento.",
        "pilares": [{"nombre": "Excelencia operacional", "descripcion": "Procesos.",
                     "milestones": {"anio1": ["Mapear procesos"], "anio2": ["Certificar"], "anio3": ["Automatizar 50%"]}}],
    }
    pdf = build_roadmap_pdf(roadmap, "Keting Media")
    assert pdf[:5] == b"%PDF-" and len(pdf) > 1000


def test_pdf_roadmap_vacio_no_truena():
    assert build_roadmap_pdf({}, None)[:5] == b"%PDF-"
