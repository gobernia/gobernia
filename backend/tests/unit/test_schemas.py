"""
Verifica que todos los schemas del Memory Buffer son válidos e instanciables.
"""
import uuid
from datetime import datetime, timezone

import pytest

from app.schemas.enums import (
    AgentTone, AgentType, BoardStatus, BranchCount, ChallengeType,
    DirectiveRole, EmployeeRange, FamilyGeneration, FunctionalArea,
    IndustryType, RevenueRange, YearsOperating,
)
from app.schemas.memory_buffer import (
    CompanyLocation, GoberniaMemoryBuffer, Stage1Company, TeamMember,
)


def test_stage1_schema_valid():
    company = Stage1Company(
        name="Empresa Demo S.A. de C.V.",
        industry=IndustryType.manufacturing,
        location=CompanyLocation(city="Monterrey", state="Nuevo León"),
        years_operating=YearsOperating.mature,
        employees=EmployeeRange.medium,
        annual_revenue=RevenueRange.five_to_15m,
        branches=BranchCount.two_to_five,
        is_family_business=True,
        family_generation=FamilyGeneration.second,
        has_family_protocol=False,
        has_board=BoardStatus.in_progress,
    )
    assert company.name == "Empresa Demo S.A. de C.V."
    assert company.is_family_business is True
    assert company.family_generation == FamilyGeneration.second


def test_team_member_schema_valid():
    member = TeamMember(
        name="Carlos García",
        role=DirectiveRole.ceo,
        is_family=True,
        makes_key_decisions=True,
        email="carlos@empresa.com",
    )
    assert member.makes_key_decisions is True


def test_memory_buffer_initializes_empty():
    session_id = uuid.uuid4()
    buffer = GoberniaMemoryBuffer(
        session_id=session_id,
        user_id="user_clerk_123",
        onboarding_started_at=datetime.now(timezone.utc),
    )
    assert buffer.completed_stages == []
    assert buffer.company is None
    assert buffer.team == []
    assert buffer.priorities == []


def test_memory_buffer_stage_tracking():
    buffer = GoberniaMemoryBuffer(
        session_id=uuid.uuid4(),
        user_id="user_clerk_123",
        completed_stages=[1, 2],
        onboarding_started_at=datetime.now(timezone.utc),
    )
    assert 1 in buffer.completed_stages
    assert 2 in buffer.completed_stages
    assert 3 not in buffer.completed_stages
