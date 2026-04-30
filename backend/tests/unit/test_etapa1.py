"""
Tests unitarios de Etapa 1.
Verifican la lógica de condicionales del spec sin tocar la DB.
"""
import pytest
from pydantic import ValidationError

from app.schemas.enums import (
    BoardStatus, BranchCount, EmployeeRange, FamilyGeneration,
    IndustryType, RevenueRange, YearsOperating,
)
from app.schemas.etapa1 import Etapa1Input
from app.services.ai.memory_buffer import (
    build_company_narrative,
    evaluate_etapa1_modules,
)


def _base_input(**overrides) -> Etapa1Input:
    defaults = dict(
        company_name="Empresa Demo S.A.",
        industry=IndustryType.manufacturing,
        location_city="Monterrey",
        location_state="Nuevo León",
        years_operating=YearsOperating.mature,
        employees=EmployeeRange.medium,
        annual_revenue=RevenueRange.five_to_15m,
        branches=BranchCount.single,
        is_family_business=False,
        has_board=BoardStatus.yes,
    )
    defaults.update(overrides)
    return Etapa1Input(**defaults)


# ── Condicionales de módulos ───────────────────────────────────────────────────

def test_no_modules_for_simple_company():
    data = _base_input()
    assert evaluate_etapa1_modules(data) == []


def test_family_module_activated():
    data = _base_input(
        is_family_business=True,
        family_generation=FamilyGeneration.second,
        has_family_protocol=False,
    )
    modules = evaluate_etapa1_modules(data)
    assert "family" in modules


def test_multi_site_module_activated():
    data = _base_input(branches=BranchCount.six_plus)
    assert "multi_site" in evaluate_etapa1_modules(data)


def test_advanced_metrics_by_employees():
    data = _base_input(employees=EmployeeRange.large)
    assert "advanced_metrics" in evaluate_etapa1_modules(data)


def test_advanced_metrics_by_revenue():
    data = _base_input(annual_revenue=RevenueRange.plus_15m)
    assert "advanced_metrics" in evaluate_etapa1_modules(data)


def test_all_modules_combined():
    data = _base_input(
        is_family_business=True,
        family_generation=FamilyGeneration.first,
        has_family_protocol=True,
        branches=BranchCount.six_plus,
        employees=EmployeeRange.large,
    )
    modules = evaluate_etapa1_modules(data)
    assert "family" in modules
    assert "multi_site" in modules
    assert "advanced_metrics" in modules


# ── Validaciones condicionales del spec ───────────────────────────────────────

def test_family_fields_required_when_is_family():
    with pytest.raises(ValidationError) as exc:
        _base_input(is_family_business=True)  # sin family_generation ni has_family_protocol
    assert "family_generation" in str(exc.value)


def test_family_fields_cleared_when_not_family():
    data = _base_input(is_family_business=False)
    assert data.family_generation is None
    assert data.has_family_protocol is None


def test_industry_custom_required_when_other():
    with pytest.raises(ValidationError):
        _base_input(industry=IndustryType.other)  # sin industry_custom


def test_industry_custom_valid_when_other():
    data = _base_input(industry=IndustryType.other, industry_custom="Minería")
    assert data.industry_custom == "Minería"


# ── Narrativa para agentes IA ─────────────────────────────────────────────────

def test_narrative_contains_company_name():
    data = _base_input(company_name="TechCorp México")
    narrative = build_company_narrative(data, [])
    assert "TechCorp México" in narrative


def test_narrative_mentions_family_generation():
    data = _base_input(
        is_family_business=True,
        family_generation=FamilyGeneration.second,
        has_family_protocol=False,
    )
    narrative = build_company_narrative(data, ["family"])
    assert "familiar" in narrative.lower()
    assert "2nd" in narrative


def test_narrative_mentions_multi_site():
    data = _base_input(branches=BranchCount.six_plus)
    narrative = build_company_narrative(data, ["multi_site"])
    assert "múltiples" in narrative.lower()
