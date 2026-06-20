import json
from app.services.ai.todd import areas
from app.services.ai.todd.agent import (
    build_system_prompt, build_anthropic_messages, parse_turn,
    enforce_coverage, state_to_memory_buffer,
)


def test_areas_son_siete():
    assert areas.AREAS == ["estrategia", "comercial", "operativo", "rh", "financiero", "legal", "familiar"]
    assert all(areas.AREA_BANK.get(a) for a in areas.AREAS)


def test_system_prompt_incluye_banco_y_esenciales():
    p = build_system_prompt()
    assert "estrategia" in p.lower() and "financiero" in p.lower()
    assert "todd" in p.lower()
    assert "competidor" in p.lower() or "industria" in p.lower()


def test_system_prompt_incluye_estado_cuando_se_pasa():
    p = build_system_prompt({"company": {"name": "Keting Media"}, "areas_cubiertas": ["estrategia"]})
    assert "Keting Media" in p and "ESTADO ACUMULADO" in p


def test_build_anthropic_messages_antepone_kickoff_y_alterna():
    history = [
        {"role": "todd", "text": "Hola, soy Todd. ¿Cómo se llama tu empresa?"},
        {"role": "user", "text": "Keting Media"},
    ]
    msgs = build_anthropic_messages(history)
    assert msgs[0]["role"] == "user"
    assert msgs[1] == {"role": "assistant", "content": "Hola, soy Todd. ¿Cómo se llama tu empresa?"}
    assert msgs[2] == {"role": "user", "content": "Keting Media"}
    roles = [m["role"] for m in msgs]
    assert roles[-1] == "user"
    for a, b in zip(roles, roles[1:]):
        assert a != b


def test_build_anthropic_messages_vacio_solo_kickoff():
    msgs = build_anthropic_messages([])
    assert len(msgs) == 1 and msgs[0]["role"] == "user"


def test_parse_turn_json_valido():
    raw = json.dumps({
        "message": "¿Tienen misión y visión por escrito?",
        "options": ["Sí", "Más o menos", "No"],
        "input": "single_choice",
        "state": {"company": {"name": "Keting Media"}, "areas_cubiertas": ["estrategia"]},
        "done": False,
    })
    t = parse_turn(raw)
    assert t["message"].startswith("¿Tienen")
    assert t["options"] == ["Sí", "Más o menos", "No"]
    assert t["input"] == "single_choice"
    assert t["state"]["company"]["name"] == "Keting Media"
    assert t["done"] is False


def test_parse_turn_basura_devuelve_defaults_seguros():
    t = parse_turn("esto no es json")
    assert isinstance(t["message"], str)
    assert t["options"] is None
    assert t["input"] == "text"
    assert t["state"] == {}
    assert t["done"] is False


def test_enforce_coverage_bloquea_done_sin_las_7_areas():
    turn = {"done": True, "state": {"areas_cubiertas": ["estrategia", "comercial"]}}
    assert enforce_coverage(turn)["done"] is False


def test_enforce_coverage_permite_done_con_las_7():
    turn = {"done": True, "state": {"areas_cubiertas": areas.AREAS}}
    assert enforce_coverage(turn)["done"] is True


def test_state_to_memory_buffer_mapea_estructura_de_la_app():
    state = {
        "company": {"name": "Keting Media", "industry": "Apps"},
        "kpis": {"financieros": [{"label": "Margen neto", "current_value": 6}]},
        "vision": {"statement": "Crecer 3 años"},
        "governance": {"score": 55, "level": "En desarrollo"},
        "narrative": "Resumen.",
        "hallazgos": {"estrategia": [{"tipo": "fortaleza", "texto": "Tiene visión"}]},
        "areas_cubiertas": areas.AREAS,
    }
    mb = state_to_memory_buffer(state)
    assert mb["company"]["name"] == "Keting Media"
    assert mb["kpis"]["financieros"][0]["label"] == "Margen neto"
    assert mb["vision"]["statement"] == "Crecer 3 años"
    assert mb["governance"]["score"] == 55
    assert mb["ai_context"]["company_narrative"] == "Resumen."
    assert mb["hallazgos"]["estrategia"][0]["tipo"] == "fortaleza"
