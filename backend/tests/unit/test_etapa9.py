"""
Tests unitarios de Etapa 9 — agentes IA y lógica de análisis.
"""
from unittest.mock import MagicMock, patch

import pytest

from app.services.ai.agents.base import (
    _build_company_context,
    _build_kpi_context,
    _build_history_context,
    _parse_json,
    _placeholder_analysis,
    run_agent_analysis,
    run_agent_chat,
    VALID_AGENTS,
    AGENT_SYSTEM_PROMPTS,
)


def _buf(tone="formal", sensitivity="medium"):
    return {
        "company": {"industry": "manufacturing"},
        "ai_context": {"company_narrative": "Empresa Demo SA de CV."},
        "vision": {"statement": "Ser líderes en 5 años."},
        "governance": {"score": 75.0, "level": "Consolidado"},
        "agent_configs": {
            agent: {"tone": tone, "alert_sensitivity": sensitivity}
            for agent in ["CFO", "CSO", "CRO", "Auditor"]
        },
    }


def _kpi_snapshot():
    return {
        "finance": [
            {"label": "Ingresos mensuales", "unit": "MXN",
             "current_value": 500000, "benchmark": None, "alert": None},
            {"label": "Margen operativo", "unit": "%",
             "current_value": 5.0, "benchmark": 15.0, "alert": "Margen bajo"},
        ]
    }


# ── Construcción de contexto ──────────────────────────────────────────────────

def test_build_company_context_incluye_narrativa():
    ctx = _build_company_context(_buf())
    assert "Empresa Demo" in ctx


def test_build_company_context_incluye_vision():
    ctx = _build_company_context(_buf())
    assert "líderes" in ctx


def test_build_company_context_incluye_governance():
    ctx = _build_company_context(_buf())
    assert "75.0" in ctx


def test_build_kpi_context_sin_datos():
    ctx = _build_kpi_context(None)
    assert "No ingresados" in ctx


def test_build_kpi_context_con_datos():
    ctx = _build_kpi_context(_kpi_snapshot())
    assert "Ingresos mensuales" in ctx
    assert "500000" in ctx


def test_build_kpi_context_alerta_marcada():
    ctx = _build_kpi_context(_kpi_snapshot())
    assert "⚠️" in ctx or "ALERTA" in ctx


def test_build_history_context_vacio():
    ctx = _build_history_context([])
    assert ctx == ""


def test_build_history_context_con_datos():
    history = [{"period": "Enero 2025", "summary": "Buen mes financiero."}]
    ctx = _build_history_context(history)
    assert "Enero 2025" in ctx
    assert "Buen mes" in ctx


# ── Prompts de sistema por agente ─────────────────────────────────────────────

def test_todos_los_agentes_tienen_prompt():
    for agent in ["CFO", "CSO", "CRO", "Auditor"]:
        assert agent in AGENT_SYSTEM_PROMPTS
        assert len(AGENT_SYSTEM_PROMPTS[agent]) > 50


def test_cfo_prompt_menciona_finanzas():
    assert "financ" in AGENT_SYSTEM_PROMPTS["CFO"].lower()


def test_auditor_prompt_menciona_gobierno():
    assert "gobierno" in AGENT_SYSTEM_PROMPTS["Auditor"].lower() or \
           "gobern" in AGENT_SYSTEM_PROMPTS["Auditor"].lower()


# ── Placeholder y parseo JSON ─────────────────────────────────────────────────

def test_placeholder_tiene_estructura_correcta():
    p = _placeholder_analysis("CFO", 2025, 4)
    assert "summary" in p
    assert "findings" in p
    assert "alerts" in p
    assert "recommendations" in p
    assert "CFO" in p["summary"]


def test_parse_json_valido():
    raw = '{"summary": "S", "findings": ["f1"], "alerts": [], "recommendations": ["r1"]}'
    result = _parse_json(raw, "CSO", 2025, 4)
    assert result["summary"] == "S"


def test_parse_json_invalido_devuelve_placeholder():
    result = _parse_json("texto sin json válido aquí", "CRO", 2025, 4)
    assert "summary" in result
    assert "CRO" in result["summary"]


def test_parse_json_con_texto_extra():
    raw = 'Aquí va el análisis: {"summary": "Ok", "findings": [], "alerts": [], "recommendations": []} fin.'
    result = _parse_json(raw, "Auditor", 2025, 5)
    assert result["summary"] == "Ok"


# ── run_agent_analysis sin API key ────────────────────────────────────────────

def test_run_analysis_sin_api_key_devuelve_placeholder():
    with patch("app.services.ai.agents.base.settings") as mock_settings:
        mock_settings.ANTHROPIC_API_KEY = ""
        result = run_agent_analysis("CFO", _buf(), _kpi_snapshot(), 2025, 4)
    assert "summary" in result
    assert isinstance(result["findings"], list)


def test_run_analysis_con_api_key_llama_claude():
    mock_response = MagicMock()
    mock_response.content = [MagicMock(
        text='{"summary": "Análisis CFO", "findings": ["f1"], "alerts": [], "recommendations": ["r1"]}'
    )]
    with patch("app.services.ai.agents.base.settings") as mock_settings, \
         patch("app.services.ai.agents.base.anthropic.Anthropic") as mock_client:
        mock_settings.ANTHROPIC_API_KEY = "test-key"
        mock_settings.AI_MODEL = "claude-sonnet-4-6"
        mock_client.return_value.messages.create.return_value = mock_response
        result = run_agent_analysis("CFO", _buf(), _kpi_snapshot(), 2025, 4)
    assert result["summary"] == "Análisis CFO"


# ── run_agent_chat sin API key ────────────────────────────────────────────────

def test_run_chat_sin_api_key_devuelve_placeholder():
    with patch("app.services.ai.agents.base.settings") as mock_settings:
        mock_settings.ANTHROPIC_API_KEY = ""
        result = run_agent_chat("CFO", "¿Cómo está el margen?", _buf(), _kpi_snapshot(), [], 2025, 4)
    assert "CFO" in result or "ANTHROPIC_API_KEY" in result


def test_run_chat_con_api_key_llama_claude():
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text="El margen está bajo el benchmark.")]
    with patch("app.services.ai.agents.base.settings") as mock_settings, \
         patch("app.services.ai.agents.base.anthropic.Anthropic") as mock_client:
        mock_settings.ANTHROPIC_API_KEY = "test-key"
        mock_settings.AI_MODEL = "claude-sonnet-4-6"
        mock_client.return_value.messages.create.return_value = mock_response
        result = run_agent_chat("CFO", "¿Cómo está el margen?", _buf(), _kpi_snapshot(), [], 2025, 4)
    assert "margen" in result.lower()
