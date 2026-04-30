"""
Inferencias de IA para Etapa 2 — Equipo Directivo.
El spec define exactamente qué concluye la IA de los datos del equipo.
"""
from app.schemas.enums import CentralizationLevel, DirectiveRole, FunctionalArea
from app.schemas.etapa2 import Etapa2Input, TeamInferencesOutput

# Mapeo rol → área funcional que cubre
_ROLE_TO_AREA: dict[DirectiveRole, FunctionalArea] = {
    DirectiveRole.cfo:        FunctionalArea.finance,
    DirectiveRole.commercial: FunctionalArea.commercial,
    DirectiveRole.operations: FunctionalArea.operations,
    DirectiveRole.hr:         FunctionalArea.hr,
    DirectiveRole.ceo:        FunctionalArea.strategy,
}

# Áreas que deben estar cubiertas para no generar gap
_REQUIRED_AREAS = {
    FunctionalArea.finance,
    FunctionalArea.commercial,
    FunctionalArea.operations,
    FunctionalArea.hr,
}


def infer_centralization(data: Etapa2Input) -> CentralizationLevel:
    """
    Spec: si solo 1 persona tiene 'toma decisiones clave' = Sí → alta centralización.
    """
    decision_makers = sum(1 for m in data.team if m.makes_key_decisions)
    if decision_makers <= 1:
        return CentralizationLevel.high
    if decision_makers <= 3:
        return CentralizationLevel.medium
    return CentralizationLevel.low


def infer_functional_gaps(data: Etapa2Input) -> list[FunctionalArea]:
    """
    Spec: detecta qué áreas funcionales no tienen cobertura en el equipo directivo.
    Sin Finanzas → CFO Agent escala urgencia.
    Sin Operaciones → alerta Auditor.
    Sin Comercial → alerta CSO.
    """
    covered = {
        _ROLE_TO_AREA[m.role]
        for m in data.team
        if m.role in _ROLE_TO_AREA
    }
    return sorted(_REQUIRED_AREAS - covered, key=lambda x: x.value)


def infer_family_concentration(data: Etapa2Input) -> float:
    """
    Spec: si >60% del equipo directivo es familiar → alerta de riesgo de gobernanza.
    """
    if not data.team:
        return 0.0
    family_count = sum(1 for m in data.team if m.is_family)
    return round(family_count / len(data.team) * 100, 1)


def infer_continuity_risk(centralization: CentralizationLevel) -> bool:
    """
    Spec: decisiones concentradas en 1 persona → alerta de continuidad operativa.
    """
    return centralization == CentralizationLevel.high


def build_alerts(
    centralization: CentralizationLevel,
    gaps: list[FunctionalArea],
    family_concentration: float,
    continuity_risk: bool,
    is_family_business: bool,
) -> list[str]:
    alerts: list[str] = []

    if continuity_risk:
        alerts.append(
            "Solo una persona toma decisiones clave. "
            "Riesgo de continuidad operativa si esa persona no está disponible."
        )

    gap_labels = {
        FunctionalArea.finance:    "Finanzas (CFO)",
        FunctionalArea.commercial: "Comercial / Ventas",
        FunctionalArea.operations: "Operaciones",
        FunctionalArea.hr:         "Recursos Humanos",
    }
    for gap in gaps:
        alerts.append(f"Sin responsable de {gap_labels.get(gap, gap.value)} en el equipo directivo.")

    if is_family_business and family_concentration > 60:
        alerts.append(
            f"{family_concentration}% del equipo directivo es familia. "
            "Riesgo de concentración familiar en la toma de decisiones."
        )

    return alerts


def run_etapa2_inferences(data: Etapa2Input, is_family_business: bool) -> TeamInferencesOutput:
    centralization = infer_centralization(data)
    gaps = infer_functional_gaps(data)
    family_concentration = infer_family_concentration(data)
    continuity_risk = infer_continuity_risk(centralization)
    alerts = build_alerts(
        centralization, gaps, family_concentration, continuity_risk, is_family_business
    )
    return TeamInferencesOutput(
        centralization_level=centralization,
        functional_gaps=gaps,
        family_concentration=family_concentration,
        continuity_risk=continuity_risk,
        alerts=alerts,
    )


def build_etapa2_memory(data: Etapa2Input, inferences: TeamInferencesOutput) -> dict:
    return {
        "team": [
            {
                "name": m.name,
                "role": m.role.value,
                "role_custom": m.role_custom,
                "is_family": m.is_family,
                "makes_key_decisions": m.makes_key_decisions,
                "email": str(m.email) if m.email else None,
            }
            for m in data.team
        ],
        "team_inferences": {
            "centralization_level": inferences.centralization_level.value,
            "functional_gaps": [g.value for g in inferences.functional_gaps],
            "family_concentration": inferences.family_concentration,
            "continuity_risk": inferences.continuity_risk,
            "alerts": inferences.alerts,
        },
    }
