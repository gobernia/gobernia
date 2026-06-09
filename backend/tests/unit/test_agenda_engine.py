from datetime import date, timedelta
from types import SimpleNamespace

from app.services.governance.agenda_engine import build_agenda

TODAY = date(2026, 6, 15)


def _task(title, status, due):
    return SimpleNamespace(title=title, status=status, due_date=due)


def _theme(key, label):
    return SimpleNamespace(key=key, label=label)


def test_kpi_detector_solo_off_track():
    kpis = [
        {"label": "Margen", "value": 8, "target": 15, "unit": "%", "on_track": False},
        {"label": "Liquidez", "value": 2, "target": 1, "unit": "x", "on_track": True},
    ]
    ag = build_agenda([], [], kpis, [], TODAY)
    kpi = [i for i in ag if i["detector"] == "DesviaciónKPI"]
    assert len(kpi) == 1
    assert "Margen" in kpi[0]["titulo"]
    assert kpi[0]["impacto"] == "alto"
    assert kpi[0]["evidencia"]


def test_compromiso_vencido_agregado():
    tasks = [
        _task("Pagar X", "pendiente", TODAY - timedelta(days=3)),
        _task("Hecho", "completada", TODAY - timedelta(days=3)),  # no cuenta
    ]
    ag = build_agenda([], [], [], tasks, TODAY)
    item = next(i for i in ag if i["detector"] == "CompromisoVencido")
    assert "1 acuerdo" in item["titulo"]
    assert item["urgencia"] == "alta"


def test_compromiso_por_vencer():
    tasks = [_task("Y", "en_progreso", TODAY + timedelta(days=3))]
    ag = build_agenda([], [], [], tasks, TODAY)
    assert any(i["detector"] == "CompromisoPorVencer" for i in ag)


def test_cobertura_critico_boost():
    themes = [_theme("aud", "Auditoría")]
    rows = [{"key": "aud", "label": "Auditoría", "esperadas": 4, "realizadas": 0, "estado": "critico"}]
    ag = build_agenda(themes, rows, [], [], TODAY)
    item = next(i for i in ag if i["detector"] == "TemaDeCobertura")
    assert item["score"] == 30.0
    assert item["urgencia"] == "alta"
    assert item["impacto"] == "alto"


def test_orden_por_score():
    themes = [_theme("fin", "Finanzas")]  # cobertura en_tiempo -> 10
    rows = [{"key": "fin", "label": "Finanzas", "esperadas": 1, "realizadas": 1, "estado": "en_tiempo"}]
    kpis = [{"label": "Margen", "value": 8, "target": 15, "unit": "%", "on_track": False}]  # 30
    ag = build_agenda(themes, rows, kpis, [], TODAY)
    assert ag[0]["detector"] == "DesviaciónKPI"
    assert ag[0]["orden"] == 1


def test_max_7():
    themes = [_theme(f"t{i}", f"Tema {i}") for i in range(10)]
    rows = [{"key": f"t{i}", "label": f"Tema {i}", "esperadas": 0, "realizadas": 0, "estado": "en_tiempo"} for i in range(10)]
    ag = build_agenda(themes, rows, [], [], TODAY)
    assert len(ag) == 7
    assert [i["orden"] for i in ag] == list(range(1, 8))


def test_vacio():
    assert build_agenda([], [], [], [], TODAY) == []
