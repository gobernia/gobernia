from datetime import date, timedelta
from types import SimpleNamespace

from app.services.governance.alerts import compute_alerts

TODAY = date(2026, 6, 15)


def _task(status, due):
    return SimpleNamespace(status=status, due_date=due)


def test_acuerdo_vencido_critical():
    a = compute_alerts([_task("pendiente", TODAY - timedelta(days=5))], [], [], TODAY)
    assert any(x["level"] == "critical" and x["category"] == "acuerdo" for x in a)


def test_acuerdo_por_vencer_warning():
    a = compute_alerts([_task("en_progreso", TODAY + timedelta(days=3))], [], [], TODAY)
    assert any(x["category"] == "acuerdo" and "próximos 7 días" in x["message"] for x in a)


def test_completada_no_alerta():
    assert compute_alerts([_task("completada", TODAY - timedelta(days=5))], [], [], TODAY) == []


def test_cobertura_critico_y_atrasado():
    rows = [
        {"label": "Auditoría", "esperadas": 4, "realizadas": 1, "estado": "atrasado"},
        {"label": "Sucesión", "esperadas": 2, "realizadas": 0, "estado": "critico"},
        {"label": "Finanzas", "esperadas": 1, "realizadas": 1, "estado": "en_tiempo"},
    ]
    a = compute_alerts([], rows, [], TODAY)
    levels = {(x["level"], x["category"]) for x in a}
    assert ("critical", "cobertura") in levels
    assert ("warning", "cobertura") in levels
    assert all("Finanzas" not in x["message"] for x in a)
    assert a[0]["level"] == "critical"


def test_kpi_off_track():
    sig = [
        {"label": "Margen", "value": 8, "target": 15, "unit": "%", "on_track": False},
        {"label": "Liquidez", "value": 2, "target": 1, "unit": "x", "on_track": True},
    ]
    a = compute_alerts([], [], sig, TODAY)
    assert any(x["category"] == "kpi" and "Margen" in x["message"] for x in a)
    assert all("Liquidez" not in x["message"] for x in a)


def test_sin_alertas():
    assert compute_alerts([], [], [], TODAY) == []


def test_criticos_antes_que_warnings():
    tasks = [_task("pendiente", TODAY - timedelta(days=1)), _task("pendiente", TODAY + timedelta(days=2))]
    a = compute_alerts(tasks, [], [], TODAY)
    assert a[0]["level"] == "critical"
