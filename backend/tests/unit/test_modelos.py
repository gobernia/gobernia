"""Llamadas según la generación del modelo (app/services/ai/modelos.py).
Con la familia 4.x todo se manda igual que siempre; con Opus/Sonnet 5.5 no se fuerza la
herramienta (daría 400), se deja espacio para pensar y se comprueba que la usó."""
from types import SimpleNamespace

import pytest

from app.services.ai import modelos
from app.services.ai.agents import base

TOOL = {"name": "matriz_foda", "description": "d", "input_schema": {"type": "object", "properties": {}}}
SISTEMA = [{"type": "text", "text": "fijo", "cache_control": {"type": "ephemeral"}}]
MENSAJES = [{"role": "user", "content": "hola"}]


def _resp(*bloques, stop="end_turn"):
    return SimpleNamespace(content=list(bloques), stop_reason=stop)


USO = SimpleNamespace(type="tool_use", name="matriz_foda", input={"fortalezas": ["a"]})
TEXTO = SimpleNamespace(type="text", text="Aquí va mi análisis…")


@pytest.mark.parametrize("model,nuevo", [
    ("claude-opus-4-8", False), ("claude-sonnet-4-6", False), ("claude-haiku-4-5-20251001", False),
    ("claude-opus-5-5", True), ("claude-sonnet-5-5", True), ("claude-haiku-5-5", True),
])
def test_generacion(model, nuevo):
    assert modelos.es_generacion_nueva(model) is nuevo


def test_familia_4_se_manda_igual_que_siempre(monkeypatch):
    llamadas = []
    monkeypatch.setattr(base, "_stream_with_retry", lambda *a, **k: pytest.fail("no debe usar streaming"))
    r = modelos.pedir_herramienta(lambda client, **kw: llamadas.append(kw) or _resp(USO), "cliente",
                                  model="claude-opus-4-8", tool=TOOL, system=SISTEMA, messages=MENSAJES,
                                  max_tokens=2048, effort="medium")
    assert r.content == [USO]
    assert llamadas == [{"model": "claude-opus-4-8", "max_tokens": 2048, "system": SISTEMA,
                         "messages": MENSAJES, "tools": [TOOL],
                         "tool_choice": {"type": "tool", "name": "matriz_foda"}}]


def test_modelo_nuevo_no_fuerza_y_reintenta_si_no_uso_la_herramienta(monkeypatch):
    llamadas, respuestas = [], iter([_resp(TEXTO), _resp(TEXTO, USO, stop="tool_use")])
    monkeypatch.setattr(base, "_stream_with_retry", lambda client, **kw: llamadas.append(kw) or next(respuestas))
    r = modelos.pedir_herramienta(lambda *a, **k: pytest.fail("no debe usar la llamada 4.x"), "cliente",
                                  model="claude-opus-5-5", tool=TOOL, system=SISTEMA, messages=MENSAJES,
                                  max_tokens=2048, effort="medium")
    assert r.content[-1] is USO and len(llamadas) == 2
    for kw in llamadas:
        assert "tool_choice" not in kw
        assert kw["tools"] == [TOOL]
        assert kw["max_tokens"] == 2048 + modelos.MARGEN_PENSAMIENTO
        assert kw["output_config"] == {"effort": "medium"}
        assert kw["system"][0] == SISTEMA[0]  # la parte en caché queda intacta, la nota va al final
        assert "matriz_foda" in kw["system"][-1]["text"]
    assert "no la usaste" in llamadas[1]["system"][-1]["text"]


def test_modelo_nuevo_reintenta_si_la_herramienta_llega_mal_formada(monkeypatch):
    """Visto con Sonnet 5.5 en esfuerzo alto: el formato interno se coló en un campo de lista."""
    tool = {"name": "analisis_consejero", "description": "d", "input_schema": {
        "type": "object", "properties": {"summary": {"type": "string"}, "findings": {"type": "array"}}}}
    roto = SimpleNamespace(type="tool_use", name="analisis_consejero",
                           input={"summary": "s", "findings": '<parameter name="texto">La cartera…'})
    bien = SimpleNamespace(type="tool_use", name="analisis_consejero",
                           input={"summary": "s", "findings": [{"texto": "La cartera…"}]})
    respuestas, llamadas = iter([_resp(roto, roto), _resp(bien)]), []
    monkeypatch.setattr(base, "_stream_with_retry", lambda client, **kw: llamadas.append(kw) or next(respuestas))
    r = modelos.pedir_herramienta(None, "c", model="claude-sonnet-5-5", tool=tool, system="sis",
                                  messages=MENSAJES, max_tokens=100)
    assert r.content == [bien] and len(llamadas) == 2
    assert not modelos._entrada_valida({"summary": "s", "findings": [{"texto": "</invoke>"}]},
                                       tool["input_schema"])
    assert modelos._entrada_valida({"summary": "s"}, tool["input_schema"])  # campo ausente: lo resuelve quien pide


def test_modelo_nuevo_rechazo_no_se_reintenta(monkeypatch):
    llamadas = []
    monkeypatch.setattr(base, "_stream_with_retry",
                        lambda client, **kw: llamadas.append(kw) or _resp(stop="refusal"))
    r = modelos.pedir_herramienta(None, "c", model="claude-opus-5-5", tool=TOOL, system="sis",
                                  messages=MENSAJES, max_tokens=100)
    assert r.stop_reason == "refusal" and len(llamadas) == 1
    assert "output_config" not in llamadas[0]  # sin effort pedido, se usa el del modelo
    assert llamadas[0]["system"].startswith("sis\n\n")


def test_tope_de_max_tokens():
    assert modelos.con_espacio_para_pensar("claude-opus-5-5", 60000) == modelos.MAX_TOKENS_TOPE
    assert modelos.con_espacio_para_pensar("claude-opus-4-8", 60000) == 60000


@pytest.mark.parametrize("model,max_tokens,effort", [
    ("claude-opus-4-8", 8192, None), ("claude-opus-5-5", 8192 + modelos.MARGEN_PENSAMIENTO, "medium"),
])
def test_diagnostico_segun_modelo(monkeypatch, model, max_tokens, effort):
    from app.services.ai import diagnostico_estrategico as de
    llamadas = []
    monkeypatch.setattr(de.settings, "ANTHROPIC_API_KEY", "sk-test")
    monkeypatch.setattr(de.settings, "DIAGNOSTICO_AI_MODEL", model)
    monkeypatch.setattr(de.settings, "DIAGNOSTICO_AI_EFFORT", "medium")
    monkeypatch.setattr(de, "_stream_with_retry", lambda client, **kw: llamadas.append(kw) or _resp(
        SimpleNamespace(type="text", text='{"resumen_ejecutivo": "x"}')))
    monkeypatch.setattr(de, "parse_diagnostico", lambda raw: {"resumen_ejecutivo": "x", "fortalezas_debilidades": {}})
    monkeypatch.setattr(de, "_diagnostico_vacio", lambda c: False)
    monkeypatch.setattr(de, "attach_internal_findings", lambda c, mb: c)
    monkeypatch.setattr(de, "derive_riesgos", lambda mb, fd: [])
    de.generate_diagnostico({"company": {"name": "Prueba"}})
    assert llamadas[0]["max_tokens"] == max_tokens
    assert llamadas[0].get("output_config") == ({"effort": effort} if effort else None)


# --- Sonnet 5.5 (paso 3) ---

@pytest.mark.parametrize("model,effort,thinking,esperado", [
    ("claude-sonnet-4-6", "high", "between_tools", {}),
    ("claude-sonnet-5-5", "high", "between_tools",
     {"output_config": {"effort": "high"}, "thinking": {"type": "between_tools"}}),
    ("claude-sonnet-5-5", "low", "adaptive", {"output_config": {"effort": "low"}}),
    ("claude-sonnet-5-5", "xhigh", "between_tools", {"output_config": {"effort": "xhigh"}}),  # daría 400
    ("claude-opus-5-5", "medium", "between_tools", {"output_config": {"effort": "medium"}}),  # Opus siempre piensa
])
def test_opciones_del_modelo(model, effort, thinking, esperado):
    assert modelos.opciones_del_modelo(model, effort, thinking) == esperado


def test_texto_ignora_el_pensamiento_y_las_herramientas():
    r = _resp(SimpleNamespace(type="thinking", thinking="", signature="s"),
              SimpleNamespace(type="text", text='{"a": '), USO, SimpleNamespace(type="text", text="1}"))
    assert modelos.texto(r) == '{"a": 1}'
    assert modelos.texto(_resp(SimpleNamespace(text="sin tipo"))) == "sin tipo"  # dobles de prueba
    assert modelos.texto(_resp()) == ""


def test_pedir_texto_familia_4_igual_que_siempre(monkeypatch):
    llamadas = []
    monkeypatch.setattr(base, "_stream_with_retry", lambda *a, **k: pytest.fail("no debe usar streaming"))
    modelos.pedir_texto(lambda client, **kw: llamadas.append(kw) or _resp(TEXTO), "c",
                        model="claude-sonnet-4-6", system=SISTEMA, messages=MENSAJES, max_tokens=2048,
                        effort="high", thinking="between_tools")
    assert llamadas == [{"model": "claude-sonnet-4-6", "max_tokens": 2048, "system": SISTEMA,
                         "messages": MENSAJES}]


def test_pedir_texto_sonnet_5_5(monkeypatch):
    llamadas = []
    monkeypatch.setattr(base, "_stream_with_retry", lambda client, **kw: llamadas.append(kw) or _resp(TEXTO))
    r = modelos.pedir_texto(lambda *a, **k: pytest.fail("no debe usar la llamada 4.x"), "c",
                            model="claude-sonnet-5-5", system=SISTEMA, messages=MENSAJES, max_tokens=2048,
                            effort="high", thinking="between_tools")
    assert modelos.texto(r) == TEXTO.text
    assert llamadas == [{"model": "claude-sonnet-5-5", "max_tokens": 2048 + modelos.MARGEN_PENSAMIENTO,
                         "system": SISTEMA, "messages": MENSAJES, "output_config": {"effort": "high"},
                         "thinking": {"type": "between_tools"}}]


def test_turno_de_todd_en_vivo_con_sonnet_5_5(monkeypatch):
    """La pregunta en vivo sigue funcionando: misma vía de streaming, sin forzar la herramienta."""
    from app.services.ai.todd import agent
    llamadas = []
    turno = SimpleNamespace(type="tool_use", name="responder_turno",
                            input={"message": "¿Cuántos empleados tienen?", "input": "text", "state": {}})
    monkeypatch.setattr(agent.settings, "ANTHROPIC_API_KEY", "sk-test")
    monkeypatch.setattr(agent.settings, "AI_MODEL", "claude-sonnet-5-5")
    monkeypatch.setattr(agent.settings, "AI_EFFORT", "high")  # el turno usa el de "en vivo"
    monkeypatch.setattr(agent.settings, "AI_EFFORT_EN_VIVO", "low")
    monkeypatch.setattr(agent.settings, "AI_THINKING", "adaptive")
    monkeypatch.setattr(agent.anthropic, "Anthropic", lambda api_key: "cliente")
    monkeypatch.setattr(agent, "_create_with_retry", lambda *a, **k: pytest.fail("debe ir en vivo"))
    monkeypatch.setattr(agent, "stream_turno",
                        lambda client, al_avanzar, **kw: llamadas.append(kw) or _resp(turno, stop="tool_use"))
    t = agent.run_todd_turn([{"role": "user", "text": "Hola"}], {}, al_avanzar=lambda campos: None)
    assert t["message"] == "¿Cuántos empleados tienen?"
    assert len(llamadas) == 1 and "tool_choice" not in llamadas[0]
    assert llamadas[0]["output_config"] == {"effort": "low"} and "thinking" not in llamadas[0]
    assert "responder_turno" in llamadas[0]["system"][-1]["text"]


@pytest.mark.parametrize("model,cambia", [("claude-sonnet-4-6", True), ("claude-sonnet-5-5", False)])
def test_chat_de_todd_ultima_ronda(monkeypatch, model, cambia):
    """Con los modelos nuevos la lista de herramientas no cambia a media conversación; se avisa."""
    from app.services.ai import todd_secretario as ts
    monkeypatch.setattr(ts.settings, "AI_MODEL", model)
    tools = [ts.LEER_DOCUMENTO_TOOL, ts.BUSCAR_EXPEDIENTE_TOOL, ts.PROPONER_CAMBIO_TOOL]
    assert ts._herramientas_de_la_ronda(tools, ultima=False) == tools
    assert (ts._herramientas_de_la_ronda(tools, ultima=True)
            == [ts.PROPONER_CAMBIO_TOOL, ts.REGISTRAR_AVANCE_TOOL]) is cambia
    resultados = [{"type": "tool_result", "tool_use_id": "x", "content": "r"}]
    assert ts._resultados_de_la_ronda(resultados, 0) == resultados
    penultima = ts._resultados_de_la_ronda(resultados, ts._MAX_LECTURAS - 1)
    assert penultima == (resultados if cambia else [*resultados, ts._AVISO_ULTIMA_RONDA])
