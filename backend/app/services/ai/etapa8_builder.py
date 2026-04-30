"""
Builder de Etapa 8 — arma el bloque de Memory Buffer con visión,
expectativas y configuración de agentes.
"""
from app.schemas.etapa8 import (
    AgentConfig,
    AgentConfigSummary,
    BoardExpectations,
    Etapa8Input,
    VALID_TONES,
    VALID_SENSITIVITIES,
    VALID_FREQUENCIES,
)


def build_agent_summaries(configs: list[AgentConfig]) -> list[AgentConfigSummary]:
    return [
        AgentConfigSummary(
            agent=c.agent,
            tone=c.tone,
            tone_label=VALID_TONES[c.tone],
            alert_sensitivity=c.alert_sensitivity,
            sensitivity_label=VALID_SENSITIVITIES[c.alert_sensitivity],
            custom_instructions=c.custom_instructions,
        )
        for c in configs
    ]


def build_etapa8_memory(body: Etapa8Input) -> dict:
    """Retorna el bloque que se merge al Memory Buffer de la sesión."""
    agent_map = {
        c.agent: {
            "tone": c.tone,
            "tone_label": VALID_TONES[c.tone],
            "alert_sensitivity": c.alert_sensitivity,
            "custom_instructions": c.custom_instructions,
        }
        for c in body.agent_configs
    }

    return {
        "vision": {
            "statement": body.vision_statement,
            "goals": body.main_goals,
            "board_expectations": {
                "session_frequency": body.board_expectations.session_frequency,
                "frequency_label": VALID_FREQUENCIES[body.board_expectations.session_frequency],
                "priority_topics": body.board_expectations.priority_topics,
                "success_definition": body.board_expectations.success_definition,
            },
        },
        "agent_configs": agent_map,
    }


def update_ai_context_with_vision(memory_buffer: dict, body: Etapa8Input) -> str:
    """Appends la visión y configuración al company_narrative existente."""
    existing = memory_buffer.get("ai_context", {}).get("company_narrative", "")
    vision_block = (
        f"\n\nVISIÓN DE LA EMPRESA: {body.vision_statement}\n"
        f"OBJETIVOS PRINCIPALES: {'; '.join(body.main_goals)}\n"
        f"FRECUENCIA DE SESIONES: {VALID_FREQUENCIES[body.board_expectations.session_frequency]}\n"
        f"TEMAS PRIORITARIOS: {'; '.join(body.board_expectations.priority_topics)}"
    )
    return existing + vision_block
