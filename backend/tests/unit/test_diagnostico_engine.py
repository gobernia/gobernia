import json
from app.services.ai.diagnostico_estrategico import (
    build_prompt, parse_diagnostico, SECTION_KEYS, _diagnostico_vacio,
)

MB = {"company": {
    "name": "ACME", "industry": "software",
    "location": {"city": "CDMX", "state": "CDMX", "country": "México"},
    "website": "https://acme.com", "competitors": ["Globex", "Initech"],
}}


def test_build_prompt_incluye_semillas():
    p = build_prompt(MB)
    assert "ACME" in p and "acme.com" in p and "Globex" in p and "México" in p


def test_parse_completo():
    payload = {
        "sections": {k: f"cuerpo {k}" for k in SECTION_KEYS},
        "sources": [{"title": "Fuente", "url": "https://x.com"}],
    }
    content = parse_diagnostico(json.dumps(payload))
    assert [s["key"] for s in content["sections"]] == list(SECTION_KEYS)
    assert content["sources"][0]["url"] == "https://x.com"
    assert not _diagnostico_vacio(content)


def test_parse_basura_es_vacio():
    content = parse_diagnostico("no soy json")
    assert _diagnostico_vacio(content)


def test_parse_parcial_rellena_y_marca_vacio_si_faltan_todas():
    content = parse_diagnostico(json.dumps({"sections": {}, "sources": []}))
    assert len(content["sections"]) == len(SECTION_KEYS)
    assert _diagnostico_vacio(content)
