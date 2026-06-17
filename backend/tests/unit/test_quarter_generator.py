import json
from app.services.ai.annual_plan_generator import parse_quarter_plan, quarter_month_indices


def test_quarter_month_indices():
    assert quarter_month_indices(1, 1) == [1, 2, 3]
    assert quarter_month_indices(1, 4) == [10, 11, 12]
    assert quarter_month_indices(2, 1) == [13, 14, 15]


def test_parse_quarter_ok():
    payload = {"months": [
        {"month_in_quarter": 1, "focus": "F1", "objectives": [
            {"title": "Obj", "description": "d", "kpi_refs": ["Margen"], "tasks": [
                {"title": "Subir margen", "owner": "CFO", "priority": "alta",
                 "kpi_ref": "Margen", "required_doc": "estado de resultados", "due_day": 15}
            ]}
        ]},
        {"month_in_quarter": 2, "focus": "F2", "objectives": []},
        {"month_in_quarter": 3, "focus": "F3", "objectives": []},
    ]}
    months = parse_quarter_plan(json.dumps(payload), year=1, quarter=1)
    assert [m["month_index"] for m in months] == [1, 2, 3]
    t = months[0]["objectives"][0]["tasks"][0]
    assert t["required_doc"] == "estado de resultados"
    assert t["priority"] == "alta"
    assert t["owner"] == "CFO"


def test_parse_quarter_basura_da_3_meses_vacios():
    months = parse_quarter_plan("no json", year=1, quarter=2)
    assert [m["month_index"] for m in months] == [4, 5, 6]
    assert all(m["objectives"] == [] for m in months)
