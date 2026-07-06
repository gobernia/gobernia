# backend/tests/unit/test_roadmap_generator.py
from app.services.ai.roadmap import generate_roadmap, _roadmap_fallback

_KEYS = {"vision", "mision", "propuesta_valor", "metas_3anios",
         "resumen_foda", "resumen_entorno", "pilares"}


def test_fallback_estructura_completa_y_metas_desde_kpis_sin_inventar_target():
    mb = {"vision": {"statement": "Ser referente en 3 años"},
          "kpis": {"financiero": [{"label": "Margen neto", "current_value": 6, "unit": "%"}]}}
    dcont = {"foda": {"sintesis": "Empresa sólida con retos de rentabilidad."}}
    r = _roadmap_fallback(mb, dcont)
    assert set(r.keys()) == _KEYS
    assert r["vision"] == "Ser referente en 3 años"
    assert r["resumen_foda"] == "Empresa sólida con retos de rentabilidad."
    m = r["metas_3anios"][0]
    assert m["kpi"] == "Margen neto" and m["valor_actual"] == "6%"
    assert m["target"] == ""  # NUNCA inventa el target


def test_fallback_sin_datos_no_truena():
    r = _roadmap_fallback({}, {})
    assert set(r.keys()) == _KEYS and r["pilares"] == [] and r["metas_3anios"] == []


def test_generate_roadmap_sin_api_key_usa_fallback(monkeypatch):
    monkeypatch.setattr("app.services.ai.roadmap.settings.ANTHROPIC_API_KEY", "")
    r = generate_roadmap({"vision": {"statement": "X"}}, {})
    assert r["vision"] == "X" and "pilares" in r
