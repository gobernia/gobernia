from types import SimpleNamespace

from app.services.ai import todd_secretario as ts


def _contexto():
    return {
        "empresa": "Keting Media · Marketing",
        "tablero": {
            "total": 5,
            "por_estado": {"pendiente": 3, "en_progreso": 1, "completada": 1},
            "responsables": {"Finanzas": 2, "Ana": 1},
            "atrasadas": [
                {"task_id": "t-1", "title": "Cerrar estados financieros",
                 "owner": "Finanzas", "priority": "alta", "due_date": "2026-07-01"},
            ],
            "tareas": [
                {"task_id": "t-1", "title": "Cerrar estados financieros",
                 "status": "pendiente", "owner": "Finanzas", "priority": "alta",
                 "due_date": "2026-07-01"},
            ],
        },
        "roadmap": {"vision": "Ser líderes regionales",
                    "pilares": [{"nombre": "Finanzas sanas", "objetivo": "Ordenar caja"}]},
        "acuerdos_abiertos": [
            {"descripcion": "Contratar contador", "responsable": "Ana",
             "prioridad": "alta", "pilar": "Finanzas sanas"},
        ],
    }


# ── Herramienta ───────────────────────────────────────────────────────────────

def test_tool_requiere_task_id_y_motivo():
    req = ts.PROPONER_CAMBIO_TOOL["input_schema"]["required"]
    assert set(req) == {"task_id", "motivo"}
    assert ts.PROPONER_CAMBIO_TOOL["name"] == "proponer_cambio_de_tarea"


# ── System prompt ─────────────────────────────────────────────────────────────

def test_system_prompt_incluye_estado_real():
    prompt = ts.build_system_prompt(_contexto())
    assert "Keting Media" in prompt
    assert "Cerrar estados financieros" in prompt      # tarea
    assert "TAREAS ATRASADAS" in prompt                # atrasada listada
    assert "Ser líderes regionales" in prompt          # visión del roadmap
    assert "Contratar contador" in prompt              # acuerdo abierto
    assert "t-1" in prompt                             # el id EXACTO para el tool


# ── run_todd_secretario_turn ─────────────────────────────────────────────────

def test_turn_sin_api_key_da_reply_util_y_accion_none(monkeypatch):
    monkeypatch.setattr(ts.settings, "ANTHROPIC_API_KEY", "")
    out = ts.run_todd_secretario_turn(
        [{"role": "user", "content": "¿cómo voy?"}], _contexto())
    assert out["accion"] is None
    assert "5 tareas" in out["reply"]        # usa el dato real del tablero
    assert "atrasada" in out["reply"].lower()


def test_turn_texto_devuelve_reply_sin_accion(monkeypatch):
    monkeypatch.setattr(ts.settings, "ANTHROPIC_API_KEY", "sk-test")
    resp = SimpleNamespace(content=[
        SimpleNamespace(type="text", text="Tienes 1 tarea atrasada, de Finanzas."),
    ])
    monkeypatch.setattr(ts, "_create_with_retry", lambda *a, **k: resp)
    out = ts.run_todd_secretario_turn(
        [{"role": "user", "content": "¿cómo voy?"}], _contexto())
    assert out["accion"] is None
    assert out["reply"] == "Tienes 1 tarea atrasada, de Finanzas."


def test_turn_no_puedo_con_tarea_emite_proponer_cambio(monkeypatch):
    monkeypatch.setattr(ts.settings, "ANTHROPIC_API_KEY", "sk-test")
    resp = SimpleNamespace(content=[
        SimpleNamespace(type="text", text="Entiendo, veamos una alternativa."),
        SimpleNamespace(type="tool_use", name="proponer_cambio_de_tarea",
                        input={"task_id": "t-1", "motivo": "no puedo con la tarea X: sin presupuesto"}),
    ])
    monkeypatch.setattr(ts, "_create_with_retry", lambda *a, **k: resp)
    out = ts.run_todd_secretario_turn(
        [{"role": "user", "content": "no puedo con la tarea X, no tengo presupuesto"}],
        _contexto())
    assert out["accion"] is not None
    assert out["accion"]["tipo"] == "proponer_cambio"
    assert out["accion"]["task_id"] == "t-1"
    assert "presupuesto" in out["accion"]["motivo"]
    assert out["reply"]  # conserva el texto de Todd


def test_turn_excepcion_cae_a_fallback(monkeypatch):
    monkeypatch.setattr(ts.settings, "ANTHROPIC_API_KEY", "sk-test")
    def boom(*a, **k):
        raise RuntimeError("api down")
    monkeypatch.setattr(ts, "_create_with_retry", boom)
    out = ts.run_todd_secretario_turn([{"role": "user", "content": "hola"}], _contexto())
    assert out["accion"] is None
    assert out["reply"]
