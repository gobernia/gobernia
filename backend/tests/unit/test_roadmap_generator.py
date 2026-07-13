# backend/tests/unit/test_roadmap_generator.py
from types import SimpleNamespace
from app.services.ai.roadmap import generate_roadmap, _roadmap_fallback

_KEYS = {"vision", "mision", "propuesta_valor", "metas_3anios",
         "resumen_foda", "resumen_entorno", "pilares",
         # campos del template de presentación (opcionales, ver test_roadmap_ai.py)
         "anio_objetivo", "objetivos_estrategicos", "key_enablers", "temas_por_anio",
         "conclusion_diagnostico", "conclusion_entorno"}


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


def test_generate_roadmap_ai_branch_fuerza_target_vacio(monkeypatch):
    """AI branch must NEVER emit model-provided target; it must always be forced to ''."""
    monkeypatch.setattr("app.services.ai.roadmap.settings.ANTHROPIC_API_KEY", "test-key")

    # Mock anthropic.Anthropic constructor to avoid needing real credentials
    monkeypatch.setattr("app.services.ai.roadmap.anthropic.Anthropic", lambda **k: object())

    # Create a fake tool_use block with a roadmap that includes non-empty target
    fake_block = SimpleNamespace(
        type="tool_use",
        input={
            "vision": "Visión de prueba",
            "mision": "Misión de prueba",
            "propuesta_valor": "Propuesta de valor",
            "metas_3anios": [
                {"meta": "Meta 1", "kpi": "KPI 1", "valor_actual": "6%", "target": "99%"}  # Non-empty target from model
            ],
            "resumen_foda": "Resumen FODA",
            "resumen_entorno": "Resumen entorno",
            "pilares": []
        }
    )

    # Mock _create_with_retry to return the fake response
    fake_response = SimpleNamespace(content=[fake_block])
    monkeypatch.setattr("app.services.ai.roadmap._create_with_retry", lambda *a, **k: fake_response)

    # Call generate_roadmap and verify target is forced to ""
    r = generate_roadmap({"company": {"name": "Test Corp"}}, {})

    # Verify AI branch ran (not fallback) by checking the vision
    assert r["vision"] == "Visión de prueba"
    assert r["mision"] == "Misión de prueba"

    # CRITICAL: Verify target is forced to "" even though model returned "99%"
    assert len(r["metas_3anios"]) > 0
    assert r["metas_3anios"][0]["meta"] == "Meta 1"  # Prove AI branch ran
    assert r["metas_3anios"][0]["target"] == ""  # Target must be empty, NOT "99%"
