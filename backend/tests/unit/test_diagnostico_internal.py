from app.services.ai.diagnostico_estrategico import build_prompt, attach_internal_findings


def test_build_prompt_incluye_hallazgos_internos():
    mb = {
        "company": {"name": "Keting Media", "industry": "Apps", "website": "https://k.mx",
                    "competitors": ["Wizeline"]},
        "hallazgos": {
            "financiero": [{"tipo": "debilidad", "texto": "Márgenes apretados"}],
            "comercial": [{"tipo": "fortaleza", "texto": "Cartera diversificada"}],
        },
    }
    p = build_prompt(mb)
    assert "Keting Media" in p
    assert "Márgenes apretados" in p
    assert "fortaleza" in p.lower() or "debilidad" in p.lower()


def test_build_prompt_sin_hallazgos_no_truena():
    p = build_prompt({"company": {"name": "X"}})
    assert "X" in p


def test_build_prompt_incluye_kpis_con_valor():
    """Si la empresa SÍ reportó KPIs con número, el diagnóstico los toma en cuenta."""
    mb = {"company": {"name": "Keting Media"},
          "kpis": {"financiero": [{"label": "Margen neto", "current_value": 6, "unit": "%"}],
                   "comercial": [{"label": "Crecimiento de ventas", "current_value": 4, "unit": "%"}]}}
    p = build_prompt(mb)
    assert "Margen neto" in p
    assert "6" in p
    assert "Crecimiento de ventas" in p


def test_build_prompt_kpis_sin_valor_no_truena():
    mb = {"company": {"name": "X"},
          "kpis": {"financiero": [{"label": "Margen", "current_value": None, "unknown": True}]}}
    p = build_prompt(mb)
    assert "X" in p  # no truena; un KPI sin valor simplemente no se inyecta como dato duro


def test_build_prompt_hallazgos_forma_nota_clasificacion_no_truena():
    """Forma REAL que produce Todd: {area: {'nota': str, 'clasificacion': str}}.
    Antes reventaba con 'str object has no attribute get' al iterar el dict como lista."""
    mb = {
        "company": {"name": "Keting Media", "industry": "Software", "competitors": "No identificados"},
        "hallazgos": {
            "rh": {"nota": "No tienen proceso formal de reclutamiento", "clasificacion": "debilidad"},
            "financiero": {"nota": "Claridad de costos por proyecto", "clasificacion": "parcial"},
        },
    }
    p = build_prompt(mb)
    assert "Keting Media" in p
    assert "No tienen proceso formal de reclutamiento" in p
    assert "No identificados" in p  # competitors como string, no como lista de caracteres


def test_build_prompt_hallazgos_lista_de_strings_no_truena():
    mb = {"company": {"name": "Y"}, "hallazgos": {"legal": ["Marca registrada", "Al corriente fiscal"]}}
    p = build_prompt(mb)
    assert "Marca registrada" in p


def test_attach_internal_findings_pega_hallazgos():
    content = {"sections": [{"key": "resumen_ejecutivo", "title": "R", "body": "..."}], "sources": []}
    mb = {"hallazgos": {"rh": [{"tipo": "parcial", "texto": "Sin plan DNC"}]}}
    out = attach_internal_findings(content, mb)
    assert out["fortalezas_debilidades"]["rh"][0]["texto"] == "Sin plan DNC"
    assert out["sections"][0]["key"] == "resumen_ejecutivo"


def test_attach_internal_findings_sin_hallazgos_es_dict_vacio():
    out = attach_internal_findings({"sections": [], "sources": []}, {})
    assert out["fortalezas_debilidades"] == {}


def test_attach_internal_findings_normaliza_forma_nota_clasificacion():
    """La forma {area: {'nota','clasificacion'}} de Todd se normaliza a [{'tipo','texto'}]
    para que el frontend (items.map) no truene."""
    mb = {"hallazgos": {"rh": {"nota": "Sin proceso de reclutamiento", "clasificacion": "debilidad"}}}
    out = attach_internal_findings({"sections": [], "sources": []}, mb)
    assert out["fortalezas_debilidades"]["rh"] == [{"tipo": "debilidad", "texto": "Sin proceso de reclutamiento"}]
