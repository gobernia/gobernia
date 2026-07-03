from app.services.ai.perspectivas import roles
from app.services.ai.perspectivas.agent import build_perspectiva_prompt, run_perspectiva_turn


def test_roles_definidos():
    assert roles.ROLES == ["empleado", "directivo", "socio", "cliente", "proveedor"]
    assert roles.ANONYMOUS_ROLES == {"empleado", "cliente"}


def test_prompt_por_rol_menciona_el_rol_y_la_empresa():
    p = build_perspectiva_prompt("cliente", "Keting Media · software")
    assert "Keting Media" in p
    # el prompt de cliente NO debe pedir datos internos que un cliente no conoce (rh/finanzas)
    low = p.lower()
    assert "cliente" in low
    assert "rotación de personal" not in low and "margen neto" not in low


def test_prompt_empleado_enfoca_operacion_y_cultura():
    p = build_perspectiva_prompt("empleado", "Empresa X").lower()
    assert "empleado" in p or "equipo" in p


def test_run_perspectiva_turn_sin_api_key_devuelve_turno_minimo(monkeypatch):
    monkeypatch.setattr("app.services.ai.perspectivas.agent.settings.ANTHROPIC_API_KEY", "")
    t = run_perspectiva_turn([], None, "cliente", "Empresa X")
    assert set(t.keys()) >= {"message", "options", "input", "state", "done"}
    assert t["done"] is False
