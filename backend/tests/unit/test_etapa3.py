"""
Tests unitarios de Etapa 3 — mapeo Prioridad → Agente → Áreas.
"""
import pytest
from pydantic import ValidationError

from app.schemas.enums import AgentType, ChallengeType, FunctionalArea
from app.schemas.etapa3 import Etapa3Input, PriorityInput
from app.services.ai.etapa3_mapping import get_lead_agent, map_priorities


def _input(*challenges_with_rank) -> Etapa3Input:
    """Helper: recibe tuplas (ChallengeType, rank)."""
    return Etapa3Input(priorities=[
        PriorityInput(challenge=c, rank=r) for c, r in challenges_with_rank
    ])


# ── Mapeo agente líder (tabla del spec) ───────────────────────────────────────

def test_rentabilidad_lider_cfo():
    data = _input(
        (ChallengeType.profitability, 1),
        (ChallengeType.talent, 2),
        (ChallengeType.operations, 3),
    )
    mapped = map_priorities(data)
    assert get_lead_agent(mapped) == AgentType.cfo


def test_crecimiento_comercial_lider_cso():
    data = _input(
        (ChallengeType.commercial_growth, 1),
        (ChallengeType.profitability, 2),
        (ChallengeType.talent, 3),
    )
    assert get_lead_agent(map_priorities(data)) == AgentType.cso


def test_operacion_lider_auditor():
    data = _input(
        (ChallengeType.operations, 1),
        (ChallengeType.talent, 2),
        (ChallengeType.profitability, 3),
    )
    assert get_lead_agent(map_priorities(data)) == AgentType.auditor


def test_cumplimiento_lider_cro():
    data = _input(
        (ChallengeType.compliance_risk, 1),
        (ChallengeType.operations, 2),
        (ChallengeType.talent, 3),
    )
    assert get_lead_agent(map_priorities(data)) == AgentType.cro


def test_delegacion_lider_cso_con_soporte_cro():
    data = _input(
        (ChallengeType.delegation_succession, 1),
        (ChallengeType.talent, 2),
        (ChallengeType.profitability, 3),
    )
    mapped = map_priorities(data)
    top = next(p for p in mapped if p.rank == 1)
    assert top.lead_agent == AgentType.cso
    assert AgentType.cro in top.supporting_agents


def test_innovacion_lider_cso_con_soporte_auditor():
    data = _input(
        (ChallengeType.innovation_technology, 1),
        (ChallengeType.talent, 2),
        (ChallengeType.profitability, 3),
    )
    mapped = map_priorities(data)
    top = next(p for p in mapped if p.rank == 1)
    assert top.lead_agent == AgentType.cso
    assert AgentType.auditor in top.supporting_agents


# ── Áreas activadas ───────────────────────────────────────────────────────────

def test_rentabilidad_activa_finanzas_y_operaciones():
    data = _input(
        (ChallengeType.profitability, 1),
        (ChallengeType.talent, 2),
        (ChallengeType.operations, 3),
    )
    mapped = map_priorities(data)
    top = next(p for p in mapped if p.rank == 1)
    assert FunctionalArea.finance in top.activated_areas
    assert FunctionalArea.operations in top.activated_areas


def test_cumplimiento_activa_legal():
    data = _input(
        (ChallengeType.compliance_risk, 1),
        (ChallengeType.talent, 2),
        (ChallengeType.operations, 3),
    )
    mapped = map_priorities(data)
    top = next(p for p in mapped if p.rank == 1)
    assert FunctionalArea.legal in top.activated_areas


# ── Validaciones del schema ───────────────────────────────────────────────────

def test_menos_de_3_prioridades_falla():
    with pytest.raises(ValidationError):
        _input((ChallengeType.profitability, 1), (ChallengeType.talent, 2))


def test_mas_de_5_prioridades_falla():
    with pytest.raises(ValidationError):
        _input(
            (ChallengeType.profitability, 1),
            (ChallengeType.talent, 2),
            (ChallengeType.operations, 3),
            (ChallengeType.commercial_growth, 4),
            (ChallengeType.compliance_risk, 5),
            (ChallengeType.market_position, 6),
        )


def test_ranks_duplicados_fallan():
    with pytest.raises(ValidationError):
        Etapa3Input(priorities=[
            PriorityInput(challenge=ChallengeType.profitability, rank=1),
            PriorityInput(challenge=ChallengeType.talent, rank=1),
            PriorityInput(challenge=ChallengeType.operations, rank=2),
        ])


def test_retos_duplicados_fallan():
    with pytest.raises(ValidationError):
        Etapa3Input(priorities=[
            PriorityInput(challenge=ChallengeType.profitability, rank=1),
            PriorityInput(challenge=ChallengeType.profitability, rank=2),
            PriorityInput(challenge=ChallengeType.operations, rank=3),
        ])


def test_reto_other_sin_custom_falla():
    with pytest.raises(ValidationError):
        PriorityInput(challenge=ChallengeType.other, rank=1)


def test_reto_other_con_custom_valido():
    p = PriorityInput(challenge=ChallengeType.other, rank=1, challenge_custom="Internacionalización")
    assert p.challenge_custom == "Internacionalización"


def test_5_prioridades_validas():
    data = _input(
        (ChallengeType.profitability, 1),
        (ChallengeType.talent, 2),
        (ChallengeType.operations, 3),
        (ChallengeType.commercial_growth, 4),
        (ChallengeType.compliance_risk, 5),
    )
    assert len(data.priorities) == 5
