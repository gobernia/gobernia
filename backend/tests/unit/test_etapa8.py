"""
Tests unitarios de Etapa 8 — validaciones de schema y builder de Memory Buffer.
"""
import pytest
from pydantic import ValidationError

from app.schemas.etapa8 import (
    AgentConfig,
    BoardExpectations,
    Etapa8Input,
    VALID_AGENTS,
    VALID_TONES,
    VALID_SENSITIVITIES,
    VALID_FREQUENCIES,
)
from app.services.ai.etapa8_builder import (
    build_agent_summaries,
    build_etapa8_memory,
    update_ai_context_with_vision,
)


def _all_agents(tone="formal", sensitivity="medium"):
    return [
        AgentConfig(agent=a, tone=tone, alert_sensitivity=sensitivity)
        for a in VALID_AGENTS
    ]


def _board():
    return BoardExpectations(
        session_frequency="monthly",
        priority_topics=["Finanzas", "Crecimiento"],
        success_definition="Lograr los objetivos estratégicos del año.",
    )


def _valid_input(**kwargs):
    defaults = dict(
        vision_statement="Ser la empresa líder en gobierno corporativo de México en 5 años.",
        main_goals=["Duplicar ingresos", "Internacionalizar"],
        board_expectations=_board(),
        agent_configs=_all_agents(),
    )
    defaults.update(kwargs)
    return Etapa8Input(**defaults)


# ── Validación de visión ──────────────────────────────────────────────────────

def test_vision_valida():
    inp = _valid_input()
    assert len(inp.vision_statement) >= 20


def test_vision_muy_corta_falla():
    with pytest.raises(ValidationError):
        _valid_input(vision_statement="Corta")


def test_vision_muy_larga_falla():
    with pytest.raises(ValidationError):
        _valid_input(vision_statement="x" * 501)


def test_goals_vacios_fallan():
    with pytest.raises(ValidationError):
        _valid_input(main_goals=[])


def test_goals_max_5():
    with pytest.raises(ValidationError):
        _valid_input(main_goals=["g1", "g2", "g3", "g4", "g5", "g6"])


# ── Validación de agentes ─────────────────────────────────────────────────────

def test_agente_invalido_falla():
    with pytest.raises(ValidationError):
        AgentConfig(agent="CEO", tone="formal", alert_sensitivity="medium")


def test_tono_invalido_falla():
    with pytest.raises(ValidationError):
        AgentConfig(agent="CFO", tone="casual", alert_sensitivity="medium")


def test_sensibilidad_invalida_falla():
    with pytest.raises(ValidationError):
        AgentConfig(agent="CFO", tone="formal", alert_sensitivity="extreme")


def test_faltan_agentes_falla():
    with pytest.raises(ValidationError):
        Etapa8Input(
            vision_statement="Visión de largo plazo para la empresa.",
            main_goals=["Meta 1"],
            board_expectations=_board(),
            agent_configs=[AgentConfig(agent="CFO", tone="formal", alert_sensitivity="high")],
        )


def test_agente_duplicado_falla():
    configs = [AgentConfig(agent="CFO", tone="formal", alert_sensitivity="high")] * 2
    configs += [
        AgentConfig(agent="CSO", tone="direct", alert_sensitivity="medium"),
        AgentConfig(agent="CRO", tone="strategic", alert_sensitivity="low"),
        AgentConfig(agent="Auditor", tone="collaborative", alert_sensitivity="medium"),
    ]
    with pytest.raises(ValidationError):
        _valid_input(agent_configs=configs)


def test_los_4_agentes_validos():
    inp = _valid_input()
    agents = {c.agent for c in inp.agent_configs}
    assert agents == VALID_AGENTS


# ── Validación de expectativas ────────────────────────────────────────────────

def test_frecuencia_invalida_falla():
    with pytest.raises(ValidationError):
        BoardExpectations(
            session_frequency="weekly",
            priority_topics=["Tema"],
            success_definition="Definición de éxito clara.",
        )


def test_success_definition_corta_falla():
    with pytest.raises(ValidationError):
        BoardExpectations(
            session_frequency="monthly",
            priority_topics=["Tema"],
            success_definition="Corto",
        )


def test_topics_vacios_fallan():
    with pytest.raises(ValidationError):
        BoardExpectations(
            session_frequency="monthly",
            priority_topics=[],
            success_definition="Definición de éxito suficientemente larga.",
        )


# ── Builder de Memory Buffer ─────────────────────────────────────────────────

def test_build_memory_contiene_vision():
    inp = _valid_input()
    mem = build_etapa8_memory(inp)
    assert "vision" in mem
    assert mem["vision"]["statement"] == inp.vision_statement
    assert mem["vision"]["goals"] == inp.main_goals


def test_build_memory_contiene_los_4_agentes():
    inp = _valid_input()
    mem = build_etapa8_memory(inp)
    assert "agent_configs" in mem
    assert set(mem["agent_configs"].keys()) == VALID_AGENTS


def test_build_memory_contiene_expectativas():
    inp = _valid_input()
    mem = build_etapa8_memory(inp)
    exp = mem["vision"]["board_expectations"]
    assert exp["session_frequency"] == "monthly"
    assert "Finanzas" in exp["priority_topics"]


def test_build_agent_summaries_incluye_labels():
    inp = _valid_input(agent_configs=_all_agents("strategic", "high"))
    summaries = build_agent_summaries(inp.agent_configs)
    for s in summaries:
        assert s.tone_label == VALID_TONES["strategic"]
        assert s.sensitivity_label == VALID_SENSITIVITIES["high"]


def test_update_ai_context_agrega_vision():
    buf = {"ai_context": {"company_narrative": "Empresa Demo."}}
    inp = _valid_input()
    narrative = update_ai_context_with_vision(buf, inp)
    assert "VISIÓN" in narrative
    assert inp.vision_statement in narrative
    assert "Empresa Demo." in narrative


def test_update_ai_context_sin_narrative_previo():
    buf = {}
    inp = _valid_input()
    narrative = update_ai_context_with_vision(buf, inp)
    assert "VISIÓN" in narrative
