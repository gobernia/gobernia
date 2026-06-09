from app.services.ai import minuta as minuta_mod
from app.services.ai.minuta import generate_minuta, _rebuild_minuta

AGENDA = [
    {"titulo": "KPI Margen fuera de objetivo", "evidencia": ["Margen: 8% (meta 15%)"], "racional": "rac kpi"},
    {"titulo": "Cubrir Auditoría", "evidencia": ["Auditoría: 0 de 4"], "racional": "rac aud"},
]


def test_fallback_sin_api_key(monkeypatch):
    monkeypatch.setattr(minuta_mod.settings, "ANTHROPIC_API_KEY", "")
    out = generate_minuta(AGENDA, {}, "Junio 2026")
    assert out["carta"] == ""
    assert len(out["temas"]) == 2
    t0 = out["temas"][0]
    assert t0["id"] == 0 and t0["titulo"] == "KPI Margen fuera de objetivo"
    assert t0["sintesis"] == "rac kpi"
    assert t0["decision"]["decision_tomada"] is None
    assert t0["decision"]["opcion_a"] and t0["decision"]["opcion_b"]
    assert t0["compromiso"] is None


def test_agenda_vacia(monkeypatch):
    monkeypatch.setattr(minuta_mod.settings, "ANTHROPIC_API_KEY", "sk-test")
    assert generate_minuta([], {}, "Junio 2026") == {"carta": "", "temas": []}


def test_cap_5(monkeypatch):
    monkeypatch.setattr(minuta_mod.settings, "ANTHROPIC_API_KEY", "")
    big = [{"titulo": f"T{i}", "evidencia": [], "racional": f"r{i}"} for i in range(8)]
    out = generate_minuta(big, {}, "X")
    assert len(out["temas"]) == 5
    assert [t["id"] for t in out["temas"]] == [0, 1, 2, 3, 4]


def test_rebuild_usa_llm_y_ancla_titulo():
    temas_llm = {"0": {"sintesis": "s0", "pregunta": "p0", "opcion_a": "a0", "opcion_b": "b0"}}
    out = _rebuild_minuta(AGENDA, temas_llm)
    assert out[0]["titulo"] == "KPI Margen fuera de objetivo"  # anclado a la agenda
    assert out[0]["sintesis"] == "s0"
    assert out[0]["decision"]["pregunta"] == "p0"
    assert out[0]["decision"]["opcion_a"] == "a0"
    assert out[1]["sintesis"] == "rac aud"  # sin llm para id 1 -> fallback al racional
    assert out[1]["decision"]["opcion_a"]  # decisión genérica presente
