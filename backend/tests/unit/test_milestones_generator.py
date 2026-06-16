import json
from app.services.ai.annual_plan_generator import parse_milestones, _milestones_vacio


def test_parse_milestones_ok():
    payload = {"milestones": [
        {"type": "trimestral", "year": 1, "period": 1, "title": "Q1", "target": "11% margen", "kpi_ref": "Margen"},
        {"type": "anual", "year": 1, "period": 1, "title": "Año 1", "target": "crecer 20%", "kpi_ref": None},
    ]}
    out = parse_milestones(json.dumps(payload))
    assert out["items"][0]["type"] == "trimestral"
    assert out["items"][0]["target"] == "11% margen"
    assert out["items"][1]["kpi_ref"] is None
    assert not _milestones_vacio(out)


def test_parse_milestones_descarta_tipo_invalido():
    payload = {"milestones": [{"type": "raro", "year": 1, "period": 1, "title": "x", "target": "y"}]}
    out = parse_milestones(json.dumps(payload))
    assert out["items"] == []
    assert _milestones_vacio(out)


def test_parse_basura():
    out = parse_milestones("no json")
    assert _milestones_vacio(out)
