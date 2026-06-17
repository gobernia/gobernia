from datetime import date
from types import SimpleNamespace
from app.services.ai.month_review import compute_signals, deterministic_review


def _task(id, required_doc=None, status="pendiente"):
    return SimpleNamespace(id=id, status=status, due_date=None, required_doc=required_doc, title=f"T{id}")


def test_tasks_missing_doc_detecta_faltante():
    tasks = [
        _task("a", required_doc="estado de resultados"),   # sin evidencia → falta
        _task("b", required_doc="contrato"),               # con evidencia → ok
        _task("c", required_doc=None),                     # no pide doc → no aplica
    ]
    sig = compute_signals(tasks, {}, {}, date(2026, 3, 1), evidence_counts={"b": 1})
    titles = [m["title"] for m in sig["tasks_missing_doc"]]
    assert titles == ["Ta"]  # solo la 'a'
    assert sig["tasks_missing_doc"][0]["required_doc"] == "estado de resultados"


def test_tasks_missing_doc_vacio_sin_evidence_counts():
    tasks = [_task("a", required_doc="x")]
    sig = compute_signals(tasks, {}, {}, date(2026, 3, 1))  # sin evidence_counts
    assert sig["tasks_missing_doc"] == []


def test_deterministic_review_menciona_faltantes():
    signals = {"completion_pct": 90, "tasks_missing_doc": [{"title": "T1", "required_doc": "estado de resultados"}]}
    rev = deterministic_review(signals, [])
    assert "sustento" in rev["summary"].lower() or "documento" in rev["summary"].lower()
