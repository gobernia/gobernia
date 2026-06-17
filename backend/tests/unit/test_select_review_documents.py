from datetime import datetime, timezone, timedelta
from types import SimpleNamespace
from app.services.ai.month_review import select_review_documents, _MAX_REVIEW_DOCS

NOW = datetime(2026, 3, 1, tzinfo=timezone.utc)


def _ev(filename, task_id, key="k", minutes=0):
    return SimpleNamespace(filename=filename, action_task_id=task_id, s3_key=key,
                           created_at=NOW + timedelta(minutes=minutes))


def _task(title, required_doc=None):
    return SimpleNamespace(title=title, required_doc=required_doc)


def test_filtra_legibles_y_anota_no_legibles():
    t1 = "task-1"
    evs = [
        _ev("estado.pdf", t1, key="k1"),
        _ev("foto.png", t1, key="k2"),
        _ev("hoja.xlsx", t1, key="k3"),
        _ev("doc.docx", t1, key="k4"),
    ]
    tasks_by_id = {t1: _task("Margen 11%", required_doc="estado de resultados")}
    selected, note = select_review_documents(evs, tasks_by_id)
    keys = {s["s3_key"] for s in selected}
    assert keys == {"k1", "k2"}
    kinds = {s["s3_key"]: s["kind"] for s in selected}
    assert kinds["k1"] == "pdf" and kinds["k2"] == "image"
    assert "hoja.xlsx" in note and "doc.docx" in note
    pdf = next(s for s in selected if s["s3_key"] == "k1")
    assert "Margen 11%" in pdf["label"] and "estado de resultados" in pdf["label"]


def test_media_type_por_extension():
    t = "t"
    evs = [_ev("a.jpg", t, key="kj"), _ev("b.jpeg", t, key="kje"), _ev("c.png", t, key="kp")]
    selected, _ = select_review_documents(evs, {})
    mt = {s["s3_key"]: s["media_type"] for s in selected}
    assert mt["kj"] == "image/jpeg" and mt["kje"] == "image/jpeg" and mt["kp"] == "image/png"


def test_topa_a_max_docs_y_anota_truncado():
    t = "t"
    evs = [_ev(f"d{i}.pdf", t, key=f"k{i}", minutes=i) for i in range(_MAX_REVIEW_DOCS + 3)]
    selected, note = select_review_documents(evs, {})
    assert len(selected) == _MAX_REVIEW_DOCS
    assert str(_MAX_REVIEW_DOCS) in note
    assert selected[0]["s3_key"] == f"k{_MAX_REVIEW_DOCS + 2}"


def test_sin_evidencias_devuelve_vacio():
    selected, note = select_review_documents([], {})
    assert selected == [] and note == ""
