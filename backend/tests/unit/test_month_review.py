from app.schemas.annual_plan import CloseMonthRequest, ApplyProposalRequest


def test_close_request_kpis_default_empty():
    r = CloseMonthRequest()
    assert r.kpis == {}
    r2 = CloseMonthRequest(kpis={"Razón corriente": 1.2})
    assert r2.kpis["Razón corriente"] == 1.2


def test_apply_proposal_request():
    a = ApplyProposalRequest(proposal_id="abc")
    assert a.proposal_id == "abc"


from datetime import date
from types import SimpleNamespace
from app.services.ai.month_review import compute_signals


def _task(status, due):
    return SimpleNamespace(status=status, due_date=due)


def test_compute_signals_counts_and_pct():
    today = date(2026, 6, 15)
    tasks = [
        _task("completada", date(2026, 6, 10)),
        _task("pendiente", date(2026, 6, 1)),   # atrasada
        _task("en_progreso", date(2026, 6, 30)),
        _task("completada", None),
    ]
    s = compute_signals(tasks, {}, {"company": {}}, today)
    assert s["tasks_total"] == 4
    assert s["tasks_completed"] == 2
    assert s["tasks_overdue"] == 1
    assert s["completion_pct"] == 50


def test_compute_signals_kpi_on_track_via_engine():
    today = date(2026, 6, 15)
    buf = {"company": {"industry": "manufacturing", "employees": "11-50"}}
    s_ok = compute_signals([], {"Margen operativo": 20.0}, buf, today)
    s_bad = compute_signals([], {"Margen operativo": 5.0}, buf, today)
    assert s_ok["kpis"][0]["on_track"] is True
    assert s_bad["kpis"][0]["on_track"] is False
    assert s_ok["kpis"][0]["target"] == 15.0


def test_compute_signals_unknown_kpi_label():
    s = compute_signals([], {"KPI inventado": 1.0}, {"company": {}}, date(2026, 6, 1))
    k = s["kpis"][0]
    assert k["on_track"] is None and k["target"] is None
    assert k["value"] == 1.0


from app.services.ai.month_review import deterministic_review, parse_review


def test_deterministic_review_grades_by_pct():
    assert deterministic_review({"completion_pct": 90}, [])["grade"] == "bien"
    assert deterministic_review({"completion_pct": 60}, [])["grade"] == "mal"
    assert deterministic_review({"completion_pct": 10}, [])["grade"] == "muy_mal"


def test_deterministic_review_carryover_proposals():
    r = deterministic_review({"completion_pct": 40}, ["t1", "t2"])
    types = [p["type"] for p in r["proposals"]]
    assert types == ["carry_over_task", "carry_over_task"]
    assert r["proposals"][0]["task_id"] == "t1"


def test_parse_review_clamps_grade_and_validates_proposals():
    raw = '''{"grade":"EXCELENTE","summary":"ok","by_agent":{"CFO":"bien"},
      "proposals":[
        {"type":"new_objective","title":"Mejorar caja","kpi_refs":["Razón corriente"]},
        {"type":"carry_over_task","task_id":"t1"},
        {"type":"basura"},
        {"type":"new_task","objective_id":"o1","title":"Hacer X","priority":"ALTA"}
      ]}'''
    out = parse_review(raw, fallback_grade="mal")
    assert out["grade"] == "mal"
    assert out["summary"] == "ok"
    assert out["by_agent"]["CFO"] == "bien"
    kinds = [p["type"] for p in out["proposals"]]
    assert kinds == ["new_objective", "carry_over_task", "new_task"]
    assert out["proposals"][2]["priority"] == "alta"


def test_parse_review_garbage_uses_fallback():
    out = parse_review("no json", fallback_grade="muy_mal")
    assert out["grade"] == "muy_mal"
    assert out["proposals"] == []
