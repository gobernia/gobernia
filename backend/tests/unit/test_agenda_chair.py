import json

from app.services.ai import agenda_chair
from app.services.ai.agenda_chair import chair_curate_agenda, _rebuild

AGENDA = [
    {"orden": 1, "titulo": "A", "area": "kpi", "detector": "DesviaciónKPI",
     "impacto": "alto", "urgencia": "media", "racional": "rac A", "evidencia": ["evA"], "score": 30.0},
    {"orden": 2, "titulo": "B", "area": "cobertura", "detector": "TemaDeCobertura",
     "impacto": "bajo", "urgencia": "baja", "racional": "rac B", "evidencia": ["evB"], "score": 10.0},
]


def test_fallback_sin_api_key(monkeypatch):
    monkeypatch.setattr(agenda_chair.settings, "ANTHROPIC_API_KEY", "")
    out = chair_curate_agenda(AGENDA, {}, "Junio 2026")
    assert out == {"carta": "", "items": AGENDA}


def test_fallback_agenda_vacia(monkeypatch):
    monkeypatch.setattr(agenda_chair.settings, "ANTHROPIC_API_KEY", "sk-test")
    assert chair_curate_agenda([], {}, "Junio 2026") == {"carta": "", "items": []}


def test_rebuild_reordena_y_reescribe():
    raw = json.dumps({"carta": "Bienvenidos.", "prioridad": [1, 0],
                      "racionales": {"1": "nuevo rac B", "0": "nuevo rac A"}})
    out = _rebuild(AGENDA, raw)
    assert out["carta"] == "Bienvenidos."
    assert [i["titulo"] for i in out["items"]] == ["B", "A"]
    assert out["items"][0]["orden"] == 1 and out["items"][1]["orden"] == 2
    assert out["items"][0]["racional"] == "nuevo rac B"
    assert out["items"][0]["evidencia"] == ["evB"]  # evidencia original preservada


def test_rebuild_anexa_faltantes_y_conserva_racional():
    raw = json.dumps({"carta": "", "prioridad": [1], "racionales": {}})
    out = _rebuild(AGENDA, raw)
    assert [i["titulo"] for i in out["items"]] == ["B", "A"]  # 0 anexado al final
    assert out["items"][1]["racional"] == "rac A"  # conserva original si no hay nuevo


def test_rebuild_ignora_ids_invalidos():
    raw = json.dumps({"carta": "", "prioridad": [5, 0, "x", 1], "racionales": {}})
    out = _rebuild(AGENDA, raw)
    assert [i["titulo"] for i in out["items"]] == ["A", "B"]


def test_rebuild_json_envuelto_en_prosa():
    raw = "Claro:\n```json\n" + json.dumps({"carta": "C", "prioridad": [0, 1], "racionales": {}}) + "\n```"
    out = _rebuild(AGENDA, raw)
    assert out["carta"] == "C"
    assert [i["titulo"] for i in out["items"]] == ["A", "B"]
