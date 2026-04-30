"""
Mapeo Prioridad → Área → Agente — Etapa 3.
Tabla exacta del spec (Anexo B).
"""
from app.schemas.enums import AgentType, ChallengeType, FunctionalArea
from app.schemas.etapa3 import Etapa3Input, PriorityMapped

# Mapeo completo del spec: reto → (agente_lider, agentes_soporte, áreas_activadas)
_CHALLENGE_MAP: dict[
    ChallengeType,
    tuple[AgentType, list[AgentType], list[FunctionalArea]]
] = {
    ChallengeType.commercial_growth: (
        AgentType.cso,
        [],
        [FunctionalArea.commercial],
    ),
    ChallengeType.profitability: (
        AgentType.cfo,
        [],
        [FunctionalArea.finance, FunctionalArea.operations],
    ),
    ChallengeType.talent: (
        AgentType.cso,
        [],
        [FunctionalArea.hr],
    ),
    ChallengeType.operations: (
        AgentType.auditor,
        [],
        [FunctionalArea.operations],
    ),
    ChallengeType.organizational_clarity: (
        AgentType.cso,
        [],
        [FunctionalArea.hr, FunctionalArea.strategy],
    ),
    ChallengeType.delegation_succession: (
        AgentType.cso,
        [AgentType.cro],
        [FunctionalArea.family, FunctionalArea.strategy],
    ),
    ChallengeType.market_position: (
        AgentType.cso,
        [],
        [FunctionalArea.commercial],
    ),
    ChallengeType.compliance_risk: (
        AgentType.cro,
        [AgentType.auditor],
        [FunctionalArea.legal],
    ),
    ChallengeType.innovation_technology: (
        AgentType.cso,
        [AgentType.auditor],
        [FunctionalArea.operations, FunctionalArea.strategy],
    ),
    ChallengeType.other: (
        AgentType.cso,
        [],
        [FunctionalArea.strategy],
    ),
}


def map_priorities(data: Etapa3Input) -> list[PriorityMapped]:
    sorted_priorities = sorted(data.priorities, key=lambda p: p.rank)
    mapped = []
    for p in sorted_priorities:
        lead, supporting, areas = _CHALLENGE_MAP[p.challenge]
        mapped.append(PriorityMapped(
            challenge=p.challenge,
            challenge_custom=p.challenge_custom,
            rank=p.rank,
            lead_agent=lead,
            supporting_agents=supporting,
            activated_areas=areas,
        ))
    return mapped


def get_lead_agent(mapped: list[PriorityMapped]) -> AgentType:
    """El agente líder es el que corresponde a la prioridad #1."""
    top = next(p for p in mapped if p.rank == 1)
    return top.lead_agent


def build_etapa3_memory(mapped: list[PriorityMapped], lead_agent: AgentType) -> dict:
    return {
        "priorities": [
            {
                "challenge": p.challenge.value,
                "challenge_custom": p.challenge_custom,
                "rank": p.rank,
                "lead_agent": p.lead_agent.value,
                "supporting_agents": [a.value for a in p.supporting_agents],
                "activated_areas": [a.value for a in p.activated_areas],
            }
            for p in mapped
        ],
    }


def build_priority_narrative(mapped: list[PriorityMapped], lead_agent: AgentType) -> str:
    top3 = [p for p in mapped if p.rank <= 3]
    challenge_labels = {
        ChallengeType.commercial_growth:    "crecimiento comercial",
        ChallengeType.profitability:        "rentabilidad",
        ChallengeType.talent:               "talento y equipo",
        ChallengeType.operations:           "operación y procesos",
        ChallengeType.organizational_clarity: "claridad organizacional",
        ChallengeType.delegation_succession: "delegación y sucesión",
        ChallengeType.market_position:      "posición en el mercado",
        ChallengeType.compliance_risk:      "cumplimiento y riesgos",
        ChallengeType.innovation_technology: "innovación y tecnología",
        ChallengeType.other:                "otro",
    }
    top_labels = [
        p.challenge_custom if p.challenge == ChallengeType.other
        else challenge_labels[p.challenge]
        for p in top3
    ]
    return (
        f" Prioridades estratégicas: {', '.join(top_labels)}. "
        f"Agente líder del consejo: {lead_agent.value}."
    )
