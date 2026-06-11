from datetime import date

from app.services.ai.annual_plan_generator import (
    month_calendar, compute_active_month_index, due_date_within_month,
)


def test_month_calendar_wraps_year():
    # start en nov 2026, month_index 1 = nov 2026, 3 = ene 2027
    assert month_calendar(2026, 11, 1) == (2026, 11)
    assert month_calendar(2026, 11, 2) == (2026, 12)
    assert month_calendar(2026, 11, 3) == (2027, 1)
    assert month_calendar(2026, 11, 12) == (2027, 10)


def test_compute_active_month_index():
    start = date(2026, 5, 1)
    assert compute_active_month_index(start, date(2026, 5, 15)) == 1
    assert compute_active_month_index(start, date(2026, 7, 2)) == 3
    # antes del inicio → 1; pasado el mes 12 → 12 (cap)
    assert compute_active_month_index(start, date(2026, 4, 1)) == 1
    assert compute_active_month_index(start, date(2030, 1, 1)) == 12


def test_due_date_within_month_clamps_day():
    assert due_date_within_month(2026, 2, 31) == date(2026, 2, 28)   # feb no bisiesto
    assert due_date_within_month(2026, 6, 15) == date(2026, 6, 15)
    assert due_date_within_month(2026, 6, 0) == date(2026, 6, 1)     # piso 1


from app.services.ai.annual_plan_generator import (
    parse_skeleton, map_month_tasks, synthesize_diagnostico, fallback_skeleton,
)


def test_parse_skeleton_normaliza_12_meses():
    raw = '''{"months":[
      {"month_index":1,"focus":"Liquidez","objectives":[
        {"title":"Mejorar caja","kpi_refs":["Razón corriente"]}]}
    ]}'''
    months = parse_skeleton(raw)
    assert len(months) == 12                       # rellena hasta 12
    assert months[0]["focus"] == "Liquidez"
    assert months[0]["objectives"][0]["title"] == "Mejorar caja"
    assert months[0]["objectives"][0]["kpi_refs"] == ["Razón corriente"]
    # meses faltantes quedan con objetivos vacíos pero presentes
    assert months[11]["month_index"] == 12
    assert months[11]["objectives"] == []


def test_parse_skeleton_basura_devuelve_fallback():
    months = parse_skeleton("no soy json")
    assert len(months) == 12


def test_map_month_tasks_normaliza_campos():
    raw = '''{"tasks":[
      {"objective_index":0,"title":"Negociar línea de crédito","owner":"CFO",
       "priority":"ALTA","due_day":10,"kpi_ref":"Razón corriente","tags":["Liquidez","x"]},
      {"objective_index":9,"title":"fuera de rango"}
    ]}'''
    objectives = [{"title": "Mejorar caja"}]
    tasks = map_month_tasks(raw, objectives, year=2026, month=6)
    # la tarea con objective_index fuera de rango se descarta
    assert len(tasks) == 1
    t = tasks[0]
    assert t["objective_index"] == 0
    assert t["priority"] == "alta"
    assert t["owner"] == "CFO"
    assert t["due_date"] == "2026-06-10"
    assert t["kpi_ref"] == "Razón corriente"
    assert t["tags"] == ["liquidez", "x"]


def test_synthesize_diagnostico_concatena_resumenes():
    analyses = {
        "CFO": {"summary": "Liquidez ajustada."},
        "CSO": {"summary": "Ventas concentradas."},
    }
    text = synthesize_diagnostico(analyses)
    assert "CFO" in text and "Liquidez ajustada." in text
    assert "CSO" in text and "Ventas concentradas." in text


def test_fallback_skeleton_es_12_meses():
    sk = fallback_skeleton()
    assert len(sk) == 12
    assert all(m["month_index"] == i + 1 for i, m in enumerate(sk))


import app.services.ai.annual_plan_generator as gen


class _FakeResponse:
    def __init__(self, text):
        self.content = [type("B", (), {"text": text})()]


def test_generate_skeleton_sin_apikey_usa_fallback(monkeypatch):
    monkeypatch.setattr(gen.settings, "ANTHROPIC_API_KEY", "", raising=False)
    months = gen.generate_skeleton({"company": {"name": "Demo"}}, "Diagnóstico", kpi_labels=[])
    assert len(months) == 12


def test_generate_skeleton_con_apikey_parsea_respuesta(monkeypatch):
    monkeypatch.setattr(gen.settings, "ANTHROPIC_API_KEY", "sk-test", raising=False)
    raw = '{"months":[{"month_index":1,"focus":"Caja","objectives":[{"title":"X","kpi_refs":[]}]}]}'
    monkeypatch.setattr(gen, "_create_with_retry", lambda *a, **k: _FakeResponse(raw))
    monkeypatch.setattr(gen.anthropic, "Anthropic", lambda **k: object())
    months = gen.generate_skeleton({"company": {"name": "Demo"}}, "Diag", kpi_labels=["Caja"])
    assert months[0]["focus"] == "Caja"


def test_generate_month_tasks_con_apikey(monkeypatch):
    monkeypatch.setattr(gen.settings, "ANTHROPIC_API_KEY", "sk-test", raising=False)
    raw = '{"tasks":[{"objective_index":0,"title":"Negociar crédito","priority":"alta","due_day":10}]}'
    monkeypatch.setattr(gen, "_create_with_retry", lambda *a, **k: _FakeResponse(raw))
    monkeypatch.setattr(gen.anthropic, "Anthropic", lambda **k: object())
    tasks = gen.generate_month_tasks(
        focus="Liquidez", objectives=[{"title": "Mejorar caja"}],
        memory_buffer={"company": {"name": "Demo"}}, year=2026, month=6,
    )
    assert tasks[0]["title"] == "Negociar crédito"
    assert tasks[0]["due_date"] == "2026-06-10"


def test_generate_skeleton_reintenta_si_vacio(monkeypatch):
    """Respuesta truncada/basura la primera vez → reintenta; la segunda válida → la usa."""
    import json
    monkeypatch.setattr(gen.settings, "ANTHROPIC_API_KEY", "sk-test", raising=False)
    valido = json.dumps({"months": [
        {"month_index": 1, "focus": "F", "objectives": [{"title": "O1"}]},
    ]})
    respuestas = iter([_FakeResponse("{basura truncada"), _FakeResponse(valido)])
    calls = {"n": 0}

    def fake_create(*a, **k):
        calls["n"] += 1
        return next(respuestas)

    monkeypatch.setattr(gen, "_create_with_retry", fake_create)
    monkeypatch.setattr(gen.anthropic, "Anthropic", lambda **k: object())
    months = gen.generate_skeleton({"company": {"name": "Demo"}}, "Diag", kpi_labels=[])
    assert calls["n"] == 2
    assert months[0]["objectives"][0]["title"] == "O1"


def test_generate_skeleton_lanza_si_sigue_vacio(monkeypatch):
    """Dos respuestas ilegibles → RuntimeError (el plan debe quedar failed, no cascarón)."""
    import pytest as _pytest
    monkeypatch.setattr(gen.settings, "ANTHROPIC_API_KEY", "sk-test", raising=False)
    monkeypatch.setattr(gen, "_create_with_retry", lambda *a, **k: _FakeResponse("{basura"))
    monkeypatch.setattr(gen.anthropic, "Anthropic", lambda **k: object())
    with _pytest.raises(RuntimeError):
        gen.generate_skeleton({"company": {"name": "Demo"}}, "Diag", kpi_labels=[])
