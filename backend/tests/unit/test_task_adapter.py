from app.services.ai.task_adapter import parse_adaptacion, adapt_task, ADAPTAR_TOOL


def test_adaptar_tool_pide_los_tres_campos():
    req = ADAPTAR_TOOL["input_schema"]["required"]
    assert set(req) == {"nueva_tarea", "descripcion", "por_que"}


def test_parse_adaptacion_normaliza_y_usa_fallback():
    out = parse_adaptacion({"nueva_tarea": "  Usar plantillas legales  "})
    assert out["nueva_tarea"] == "Usar plantillas legales"
    assert out["descripcion"] == "" and out["por_que"] == ""
    # ante dict vacío usa el título de la tarea como fallback
    out2 = parse_adaptacion({}, fallback_titulo="Contratar despacho")
    assert out2["nueva_tarea"] == "Contratar despacho"


def test_adapt_task_sin_api_key_devuelve_eco(monkeypatch):
    """Sin API key (dev/tests sin red) devuelve la tarea actual como alternativa segura."""
    monkeypatch.setattr("app.services.ai.task_adapter.settings.ANTHROPIC_API_KEY", "")
    out = adapt_task("Contratar despacho de abogados", "Profesionalizar gobierno",
                     "Keting Media", "no tengo dinero")
    assert out["nueva_tarea"] == "Contratar despacho de abogados"
    assert set(out.keys()) == {"nueva_tarea", "descripcion", "por_que"}
