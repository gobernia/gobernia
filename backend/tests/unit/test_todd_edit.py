from app.services.ai.todd.agent import _normalize_turn, RESPONSE_TOOL


def test_normalize_turn_incluye_reanudar_desde_default_continuar():
    t = _normalize_turn({"message": "x", "input": "text", "state": {}, "done": False})
    assert t["reanudar_desde"] == "continuar"


def test_normalize_turn_respeta_rehacer():
    t = _normalize_turn({"message": "x", "input": "text", "state": {}, "done": False,
                         "reanudar_desde": "rehacer"})
    assert t["reanudar_desde"] == "rehacer"


def test_normalize_turn_valor_invalido_cae_a_continuar():
    t = _normalize_turn({"message": "x", "reanudar_desde": "lo_que_sea"})
    assert t["reanudar_desde"] == "continuar"


def test_response_tool_declara_reanudar_desde():
    props = RESPONSE_TOOL["input_schema"]["properties"]
    assert "reanudar_desde" in props
    assert props["reanudar_desde"]["enum"] == ["continuar", "rehacer"]
