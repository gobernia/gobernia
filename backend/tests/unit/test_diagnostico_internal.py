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
