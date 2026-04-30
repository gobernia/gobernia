"""
Tests unitarios de Etapa 2 — inferencias de IA sobre el equipo directivo.
"""
import pytest
from pydantic import ValidationError

from app.schemas.enums import CentralizationLevel, DirectiveRole, FunctionalArea
from app.schemas.etapa2 import Etapa2Input, TeamMemberInput
from app.services.ai.etapa2_inferences import (
    build_alerts,
    infer_centralization,
    infer_family_concentration,
    infer_functional_gaps,
    run_etapa2_inferences,
)


def _member(role=DirectiveRole.ceo, makes_key_decisions=True, is_family=False, **kw):
    return TeamMemberInput(
        name="Test Member", role=role,
        makes_key_decisions=makes_key_decisions,
        is_family=is_family, **kw
    )


def _team(*members) -> Etapa2Input:
    return Etapa2Input(team=list(members))


# ── Centralización ────────────────────────────────────────────────────────────

def test_centralizacion_alta_un_decisor():
    data = _team(_member(makes_key_decisions=True), _member(makes_key_decisions=False))
    assert infer_centralization(data) == CentralizationLevel.high


def test_centralizacion_media_dos_decisores():
    data = _team(_member(makes_key_decisions=True), _member(makes_key_decisions=True))
    assert infer_centralization(data) == CentralizationLevel.medium


def test_centralizacion_baja_cuatro_decisores():
    data = _team(*[_member(makes_key_decisions=True) for _ in range(4)])
    assert infer_centralization(data) == CentralizationLevel.low


# ── Gaps funcionales ──────────────────────────────────────────────────────────

def test_sin_gaps_equipo_completo():
    data = _team(
        _member(role=DirectiveRole.ceo),
        _member(role=DirectiveRole.cfo),
        _member(role=DirectiveRole.commercial),
        _member(role=DirectiveRole.operations),
        _member(role=DirectiveRole.hr),
    )
    assert infer_functional_gaps(data) == []


def test_gap_finanzas_detectado():
    data = _team(
        _member(role=DirectiveRole.ceo),
        _member(role=DirectiveRole.commercial),
        _member(role=DirectiveRole.operations),
        _member(role=DirectiveRole.hr),
    )
    gaps = infer_functional_gaps(data)
    assert FunctionalArea.finance in gaps


def test_gap_comercial_detectado():
    data = _team(
        _member(role=DirectiveRole.ceo),
        _member(role=DirectiveRole.cfo),
        _member(role=DirectiveRole.operations),
    )
    gaps = infer_functional_gaps(data)
    assert FunctionalArea.commercial in gaps
    assert FunctionalArea.hr in gaps


def test_solo_ceo_todos_los_gaps():
    data = _team(_member(role=DirectiveRole.ceo))
    gaps = infer_functional_gaps(data)
    assert FunctionalArea.finance in gaps
    assert FunctionalArea.commercial in gaps
    assert FunctionalArea.operations in gaps
    assert FunctionalArea.hr in gaps


# ── Concentración familiar ────────────────────────────────────────────────────

def test_sin_familia_concentracion_cero():
    data = _team(_member(is_family=False), _member(is_family=False))
    assert infer_family_concentration(data) == 0.0


def test_concentracion_familiar_100():
    data = _team(_member(is_family=True), _member(is_family=True))
    assert infer_family_concentration(data) == 100.0


def test_concentracion_familiar_66():
    data = _team(_member(is_family=True), _member(is_family=True), _member(is_family=False))
    assert infer_family_concentration(data) == 66.7


# ── Alertas ───────────────────────────────────────────────────────────────────

def test_alerta_continuidad_riesgo():
    alerts = build_alerts(
        CentralizationLevel.high, [], 0.0, True, False
    )
    assert any("continuidad" in a.lower() for a in alerts)


def test_alerta_gap_finanzas():
    alerts = build_alerts(
        CentralizationLevel.medium, [FunctionalArea.finance], 0.0, False, False
    )
    assert any("finanzas" in a.lower() or "cfo" in a.lower() for a in alerts)


def test_alerta_concentracion_familiar():
    alerts = build_alerts(
        CentralizationLevel.medium, [], 75.0, False, True
    )
    assert any("familia" in a.lower() for a in alerts)


def test_sin_alertas_equipo_saludable():
    alerts = build_alerts(CentralizationLevel.low, [], 30.0, False, True)
    assert alerts == []


# ── Validaciones del schema ───────────────────────────────────────────────────

def test_equipo_vacio_falla():
    with pytest.raises(ValidationError):
        Etapa2Input(team=[])


def test_sin_decisor_falla():
    with pytest.raises(ValidationError):
        _team(_member(makes_key_decisions=False))


def test_rol_other_sin_custom_falla():
    with pytest.raises(ValidationError):
        TeamMemberInput(
            name="Juan", role=DirectiveRole.other,
            makes_key_decisions=True
        )


def test_rol_other_con_custom_valido():
    m = TeamMemberInput(
        name="Juan", role=DirectiveRole.other,
        role_custom="Tecnología", makes_key_decisions=True
    )
    assert m.role_custom == "Tecnología"


# ── Integración de inferencias ────────────────────────────────────────────────

def test_inferencias_empresa_familiar_concentrada():
    data = _team(
        _member(role=DirectiveRole.ceo, is_family=True, makes_key_decisions=True),
        _member(role=DirectiveRole.cfo, is_family=True, makes_key_decisions=False),
        _member(role=DirectiveRole.operations, is_family=False, makes_key_decisions=False),
    )
    result = run_etapa2_inferences(data, is_family_business=True)
    assert result.centralization_level == CentralizationLevel.high
    assert result.continuity_risk is True
    assert result.family_concentration == pytest.approx(66.7, 0.1)
    assert any("familia" in a.lower() for a in result.alerts)
