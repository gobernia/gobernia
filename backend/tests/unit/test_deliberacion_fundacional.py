"""
La deliberación FUNDACIONAL: la primera sesión del Consejo, antes de que exista Roadmap.

Reglas que se prueban aquí:
- Con IA: shape {conclusion, prioridades, riesgos, tesis_estrategica}; prioridades acotadas a 5;
  los riesgos NO llevan `fuente` (la deliberación no tiene los documentos a la vista).
- Sin API key (o con el tool-use roto): fallback determinista con `conclusion` VACÍA — la señal
  de que el llamador debe caer a `synthesize_diagnostico` y no perder la generación del plan.
"""
from types import SimpleNamespace

import pytest

from app.services.ai.agents.deliberacion import (
    MAX_PRIORIDADES,
    _fallback_fundacional,
    run_deliberacion_fundacional,
)

_ANALYSES = {
    "CFO": {"summary": "Margen bajo presión.",
            "recommendations": ["Renegociar proveedores", "Depurar cartera"],
            "alerts": [{"nivel": "rojo", "texto": "Liquidez a 30 días", "fuente": "EEFF p.3"}]},
    "CSO": {"summary": "Concentración de clientes.",
            "recommendations": ["Abrir canal digital"],
            "alerts": [{"nivel": "ambar", "texto": "Dependencia de un cliente", "fuente": ""}]},
}
_CRITIQUES = {"CFO": {"weak_assumptions": ["asume demanda estable"]}}
_MB = {"company": {"name": "Acme"}, "vision": {"statement": "Ser referente"}}
_DCONT = {"foda": {"sintesis": "S"}, "metas_orden": ["Rentabilidad"]}


def _mock_ai(monkeypatch, payload, captured: dict | None = None):
    monkeypatch.setattr(
        "app.services.ai.agents.deliberacion.settings.ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setattr(
        "app.services.ai.agents.deliberacion.anthropic.Anthropic", lambda **k: object())
    block = SimpleNamespace(type="tool_use", name="postura_fundacional_consejo", input=payload)

    def _fake(*a, **k):
        if captured is not None:
            captured.update(k)
        return SimpleNamespace(content=[block], stop_reason="tool_use")

    monkeypatch.setattr("app.services.ai.agents.deliberacion._create_with_retry", _fake)


def test_fundacional_shape_y_tool_use_forzado(monkeypatch):
    captured: dict = {}
    _mock_ai(monkeypatch, {
        "conclusion": "  El Consejo concluye que la empresa vive de un solo cliente.  ",
        "prioridades": ["Liquidez", "Diversificar clientes", "  Margen  ", "", "Gobierno", "Sexta"],
        "riesgos": [{"nivel": "rojo", "texto": "Liquidez", "fuente": "inventada p.9"},
                    {"nivel": "marciano", "texto": "Nivel raro"},
                    {"nivel": "verde", "texto": ""},
                    "basura"],
        "tesis_estrategica": "Dejar de ser proveedor cautivo.",
    }, captured)

    r = run_deliberacion_fundacional(_ANALYSES, _CRITIQUES, _MB, _DCONT)

    assert set(r) == {"conclusion", "prioridades", "riesgos", "tesis_estrategica"}
    assert r["conclusion"] == "El Consejo concluye que la empresa vive de un solo cliente."
    assert r["tesis_estrategica"] == "Dejar de ser proveedor cautivo."
    # 3-5 prioridades, en orden, sin vacíos
    assert r["prioridades"] == ["Liquidez", "Diversificar clientes", "Margen", "Gobierno", "Sexta"]
    assert len(r["prioridades"]) <= MAX_PRIORIDADES
    # riesgos: {nivel, texto} y nada más — sin superficie para citar fuentes inventadas
    assert r["riesgos"] == [{"nivel": "rojo", "texto": "Liquidez"},
                            {"nivel": "ambar", "texto": "Nivel raro"}]
    assert all(set(x) == {"nivel", "texto"} for x in r["riesgos"])

    # tool-use forzado sobre la herramienta del Consejo
    assert captured["tool_choice"] == {"type": "tool", "name": "postura_fundacional_consejo"}
    assert captured["tools"][0]["name"] == "postura_fundacional_consejo"
    # el prompt del sistema habla como el órgano, no como cuatro asistentes
    assert "UNA SOLA VOZ" in captured["system"]
    # los análisis y las críticas son la materia prima
    prompt = captured["messages"][0]["content"]
    assert "Margen bajo presión" in prompt and "asume demanda estable" in prompt


def test_fundacional_sin_api_key_cae_al_fallback(monkeypatch):
    monkeypatch.setattr(
        "app.services.ai.agents.deliberacion.settings.ANTHROPIC_API_KEY", "")
    r = run_deliberacion_fundacional(_ANALYSES, _CRITIQUES, _MB, _DCONT)

    assert r["_fallback"] is True
    # conclusión VACÍA a propósito: el llamador cae a synthesize_diagnostico
    assert r["conclusion"] == "" and r["tesis_estrategica"] == ""
    # las prioridades se derivan de lo que los consejeros ya recomendaron
    assert r["prioridades"] == ["Renegociar proveedores", "Depurar cartera", "Abrir canal digital"]
    assert r["riesgos"] == [{"nivel": "rojo", "texto": "Liquidez a 30 días"},
                            {"nivel": "ambar", "texto": "Dependencia de un cliente"}]


@pytest.mark.parametrize("payload", [
    {},                                   # tool_use vacío
    {"conclusion": "   "},                # conclusión inservible
])
def test_fundacional_tool_use_inservible_cae_al_fallback(monkeypatch, payload):
    _mock_ai(monkeypatch, payload)
    r = run_deliberacion_fundacional(_ANALYSES, _CRITIQUES, _MB, _DCONT)
    assert r["_fallback"] is True and r["conclusion"] == ""


def test_fundacional_excepcion_de_la_api_cae_al_fallback(monkeypatch):
    _mock_ai(monkeypatch, {})
    monkeypatch.setattr(
        "app.services.ai.agents.deliberacion._create_with_retry",
        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
    r = run_deliberacion_fundacional(_ANALYSES, _CRITIQUES, _MB, _DCONT)
    assert r["_fallback"] is True


def test_fallback_sin_analisis_no_revienta():
    r = _fallback_fundacional({})
    assert r["conclusion"] == "" and r["prioridades"] == [] and r["riesgos"] == []
