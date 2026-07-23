"""
El Auditor del Consejo validando la evidencia de las tareas (`validar_evidencias`).

Reglas que se prueban:
- Con tool-use mockeado → shape correcto {task_id, estado, motivo} por tarea.
- Una tarea SIN documentos legibles → `insuficiente` (sin gastar tokens).
- Sin API key → las tareas con documentos quedan `sin_revisar` (no revienta).
- El cap de tareas por sesión deja `sin_revisar` el excedente (las más viejas).
"""
from types import SimpleNamespace

from app.services.ai.agents import validacion
from app.services.ai.agents.validacion import MAX_TAREAS_POR_SESION, validar_evidencias

_MB = {"company": {"name": "Acme"}}

# Un bloque de documento mínimo (base64 corto): suficiente para que la tarea "tenga docs".
_DOC = {"type": "document", "source": {"type": "base64", "media_type": "application/pdf", "data": "QUJD"}}


def _tarea(task_id, *, title="T", status="completada", con_doc=True):
    return {"task_id": task_id, "title": title, "status": status,
            "docs": [_DOC] if con_doc else []}


def _mock_ai(monkeypatch, payload, captured=None):
    monkeypatch.setattr(validacion.settings, "ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setattr(validacion.anthropic, "Anthropic", lambda **k: object())
    block = SimpleNamespace(type="tool_use", name="validar_evidencias", input=payload)

    def _fake(*a, **k):
        if captured is not None:
            captured.update(k)
        return SimpleNamespace(content=[block], stop_reason="tool_use")

    monkeypatch.setattr(validacion, "_create_with_retry", _fake)


def test_shape_correcto_con_tool_use(monkeypatch):
    captured: dict = {}
    payload = {"validaciones": [
        {"task_id": "t1", "estado": "validada", "motivo": "El PDF muestra el acta firmada."},
        {"task_id": "t2", "estado": "insuficiente", "motivo": "El documento no corresponde."},
    ]}
    _mock_ai(monkeypatch, payload, captured)

    r = validar_evidencias([_tarea("t1"), _tarea("t2")], _MB)
    by_id = {v["task_id"]: v for v in r}
    assert by_id["t1"] == {"task_id": "t1", "estado": "validada", "motivo": "El PDF muestra el acta firmada."}
    assert by_id["t2"]["estado"] == "insuficiente"
    # Se forzó el tool y se mandó el system prompt del Auditor.
    assert captured["tool_choice"] == {"type": "tool", "name": "validar_evidencias"}
    assert "AUDITOR" in captured["system"]


def test_estado_desconocido_se_degrada_a_insuficiente(monkeypatch):
    _mock_ai(monkeypatch, {"validaciones": [
        {"task_id": "t1", "estado": "quien_sabe", "motivo": "raro"},
    ]})
    r = validar_evidencias([_tarea("t1")], _MB)
    assert r[0]["estado"] == "insuficiente"


def test_tarea_sin_docs_legibles_es_insuficiente_sin_llamar_ia(monkeypatch):
    llamadas = {"n": 0}

    def _boom(*a, **k):
        llamadas["n"] += 1
        raise AssertionError("no debió llamarse a la IA")

    monkeypatch.setattr(validacion.settings, "ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setattr(validacion, "_create_with_retry", _boom)

    r = validar_evidencias([_tarea("t1", con_doc=False)], _MB)
    assert r == [{"task_id": "t1", "estado": "insuficiente", "motivo": r[0]["motivo"]}]
    assert r[0]["estado"] == "insuficiente" and "legible" in r[0]["motivo"]
    assert llamadas["n"] == 0


def test_fallback_sin_api_key_deja_sin_revisar(monkeypatch):
    monkeypatch.setattr(validacion.settings, "ANTHROPIC_API_KEY", "")
    r = validar_evidencias([_tarea("t1"), _tarea("t2", con_doc=False)], _MB)
    by_id = {v["task_id"]: v for v in r}
    # Con documentos pero sin IA → sin_revisar. Sin documentos → insuficiente (no necesita IA).
    assert by_id["t1"]["estado"] == "sin_revisar"
    assert by_id["t2"]["estado"] == "insuficiente"


def test_error_de_ia_deja_sin_revisar(monkeypatch):
    monkeypatch.setattr(validacion.settings, "ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setattr(validacion.anthropic, "Anthropic", lambda **k: object())

    def _boom(*a, **k):
        raise RuntimeError("API caída")

    monkeypatch.setattr(validacion, "_create_with_retry", _boom)
    r = validar_evidencias([_tarea("t1")], _MB)
    assert r[0]["estado"] == "sin_revisar"


def test_cap_deja_sin_revisar_el_excedente(monkeypatch):
    # El Auditor solo alcanza a validar MAX_TAREAS_POR_SESION; el resto queda sin_revisar.
    n = MAX_TAREAS_POR_SESION + 3
    tareas = [_tarea(f"t{i}") for i in range(n)]
    # Mockea la IA para validar exactamente las que se le mandan.
    captured: dict = {}

    def _fake_validar(*a, **k):
        captured.update(k)
        return None

    monkeypatch.setattr(validacion.settings, "ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setattr(validacion.anthropic, "Anthropic", lambda **k: object())

    def _fake(*a, **k):
        # Devuelve 'validada' para cada tarea presente en el contenido enviado.
        content = k["messages"][0]["content"]
        ids = [b["text"].split("task_id=")[1].split(" ")[0]
               for b in content if isinstance(b, dict) and b.get("type") == "text"
               and "task_id=" in b.get("text", "")]
        payload = {"validaciones": [{"task_id": i, "estado": "validada", "motivo": "ok"} for i in ids]}
        block = SimpleNamespace(type="tool_use", name="validar_evidencias", input=payload)
        return SimpleNamespace(content=[block], stop_reason="tool_use")

    monkeypatch.setattr(validacion, "_create_with_retry", _fake)

    r = validar_evidencias(tareas, _MB)
    by_id = {v["task_id"]: v for v in r}
    assert len(r) == n
    validadas = [v for v in r if v["estado"] == "validada"]
    sin_revisar = [v for v in r if v["estado"] == "sin_revisar"]
    assert len(validadas) == MAX_TAREAS_POR_SESION
    assert len(sin_revisar) == 3
    # El excedente son las ÚLTIMAS (más viejas, dado que el llamador ordena por recencia).
    assert {v["task_id"] for v in sin_revisar} == {f"t{i}" for i in range(MAX_TAREAS_POR_SESION, n)}
    assert all("alcanzó" in v["motivo"] for v in sin_revisar)
