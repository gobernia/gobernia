"""
Motor de Gobierno — Etapa 6.
Calcula el Governance Score (0-100) a partir de respuestas sobre:
  - Consejo de administración (board)
  - Cumplimiento y control (compliance)
  - Documentación corporativa (documentation)
  - Protocolo familiar (family, condicional)
"""
from app.schemas.etapa6 import (
    GovernanceDimensionScore,
    GovernanceItem,
    GovernanceItemInput,
)

_DIMENSION_LABELS = {
    "board":         "Consejo de Administración",
    "compliance":    "Cumplimiento y Control",
    "documentation": "Documentación Corporativa",
    "family":        "Gobierno Familiar",
}

# Pesos core (board+compliance+documentation) suman 85.
# Pesos familia suman 15. Total posible = 100 (familia) o 85 (no familia).
_ALL_ITEMS: list[GovernanceItem] = [
    # ── BOARD ────────────────────────────────────────────────────────────────
    GovernanceItem(
        key="has_formal_board",
        label="Consejo de administración formal",
        description="¿Cuenta con un consejo de administración formalmente constituido?",
        dimension="board", weight=15,
    ),
    GovernanceItem(
        key="board_has_external",
        label="Consejeros independientes",
        description="¿El consejo incluye al menos un consejero independiente externo?",
        dimension="board", weight=10,
    ),
    GovernanceItem(
        key="board_sessions_regular",
        label="Sesiones regulares de consejo",
        description="¿El consejo sesiona al menos 4 veces al año con convocatoria formal?",
        dimension="board", weight=8,
    ),
    GovernanceItem(
        key="board_has_agenda",
        label="Agenda y actas de sesión",
        description="¿Las sesiones cuentan con agenda previa y actas firmadas?",
        dimension="board", weight=7,
    ),
    # ── COMPLIANCE ───────────────────────────────────────────────────────────
    GovernanceItem(
        key="agreements_tracked",
        label="Seguimiento de acuerdos",
        description="¿Los acuerdos del consejo son registrados y monitoreados formalmente?",
        dimension="compliance", weight=10,
    ),
    GovernanceItem(
        key="has_financial_audit",
        label="Auditoría financiera externa",
        description="¿Los estados financieros son revisados por un auditor externo independiente?",
        dimension="compliance", weight=10,
    ),
    GovernanceItem(
        key="has_compliance_officer",
        label="Responsable de cumplimiento",
        description="¿Existe un responsable designado para cumplimiento legal y regulatorio?",
        dimension="compliance", weight=5,
    ),
    GovernanceItem(
        key="has_anti_corruption",
        label="Política anticorrupción",
        description="¿Cuenta con una política anticorrupción documentada y comunicada a toda la organización?",
        dimension="compliance", weight=5,
    ),
    # ── DOCUMENTATION ────────────────────────────────────────────────────────
    GovernanceItem(
        key="has_bylaws",
        label="Estatutos sociales actualizados",
        description="¿Los estatutos sociales están vigentes y reflejan la estructura actual de la empresa?",
        dimension="documentation", weight=10,
    ),
    GovernanceItem(
        key="has_risk_register",
        label="Registro de riesgos",
        description="¿Existe un registro formal de riesgos actualizado al menos anualmente?",
        dimension="documentation", weight=5,
    ),
    # ── FAMILY (condicional) ─────────────────────────────────────────────────
    GovernanceItem(
        key="has_family_protocol",
        label="Protocolo familiar vigente",
        description="¿La empresa cuenta con un protocolo familiar documentado y vigente?",
        dimension="family", weight=7, is_conditional=True,
    ),
    GovernanceItem(
        key="has_succession_plan",
        label="Plan de sucesión documentado",
        description="¿Existe un plan de sucesión definido para posiciones clave de dirección?",
        dimension="family", weight=5, is_conditional=True,
    ),
    GovernanceItem(
        key="has_conflict_resolution",
        label="Mecanismo de resolución de conflictos",
        description="¿Existe un mecanismo formal para resolver conflictos entre familia y empresa?",
        dimension="family", weight=3, is_conditional=True,
    ),
]

_ITEM_MAP = {item.key: item for item in _ALL_ITEMS}
_CORE_WEIGHT_TOTAL = sum(i.weight for i in _ALL_ITEMS if not i.is_conditional)   # 85
_FAMILY_WEIGHT_TOTAL = sum(i.weight for i in _ALL_ITEMS if i.is_conditional)     # 15

_RESPONSE_VALUE = {"yes": 1.0, "partial": 0.5, "no": 0.0, "na": 0.0}

_RECOMMENDATIONS = {
    "has_formal_board":        "Formalizar el consejo de administración con acta constitutiva y reglamento interno.",
    "board_has_external":      "Incorporar al menos un consejero independiente externo para mayor objetividad.",
    "board_sessions_regular":  "Establecer un calendario anual de sesiones con mínimo 4 reuniones formales.",
    "board_has_agenda":        "Implementar plantilla de agenda y actas firmadas para cada sesión de consejo.",
    "agreements_tracked":      "Usar un sistema de seguimiento de acuerdos con responsable y fecha de cierre.",
    "has_financial_audit":     "Contratar a un auditor externo independiente para revisión anual de estados financieros.",
    "has_compliance_officer":  "Designar formalmente a un responsable de cumplimiento con funciones documentadas.",
    "has_anti_corruption":     "Redactar y comunicar una política anticorrupción con mecanismos de denuncia.",
    "has_bylaws":              "Actualizar los estatutos sociales para reflejar la estructura y gobierno actuales.",
    "has_risk_register":       "Crear un registro de riesgos con probabilidad, impacto y planes de mitigación.",
    "has_family_protocol":     "Desarrollar un protocolo familiar con apoyo de un consultor especializado.",
    "has_succession_plan":     "Documentar el plan de sucesión para las posiciones directivas clave.",
    "has_conflict_resolution": "Establecer un consejo familiar o mediador externo para conflictos familia-empresa.",
}


def build_governance_items(memory_buffer: dict) -> list[GovernanceItem]:
    """Retorna ítems de gobierno filtrados según si la empresa es familiar."""
    is_family = memory_buffer.get("company", {}).get("is_family_business", False)
    return [item for item in _ALL_ITEMS if not item.is_conditional or is_family]


def _level(score: float) -> str:
    if score >= 86:
        return "Excelente"
    if score >= 66:
        return "Consolidado"
    if score >= 41:
        return "En desarrollo"
    return "Inicial"


def calculate_governance_score(
    items: list[GovernanceItem],
    inputs: list[GovernanceItemInput],
) -> tuple[float, str, list[GovernanceDimensionScore], list[str], list[str]]:
    """
    Retorna (score, level, dimension_scores, gaps, recommendations).
    El score se normaliza sobre el peso total posible de los ítems evaluados.
    """
    input_map = {i.key: i for i in inputs}
    is_family = any(item.is_conditional for item in items)
    total_possible = _CORE_WEIGHT_TOTAL + (_FAMILY_WEIGHT_TOTAL if is_family else 0)

    # Agrupar por dimensión
    by_dim: dict[str, list[GovernanceItem]] = {}
    for item in items:
        by_dim.setdefault(item.dimension, []).append(item)

    total_earned = 0.0
    gaps: list[str] = []
    recommendations: list[str] = []
    dimension_scores: list[GovernanceDimensionScore] = []

    for dim, dim_items in by_dim.items():
        dim_possible = sum(i.weight for i in dim_items)
        dim_earned = 0.0
        compliant = 0
        evaluated = 0

        for item in dim_items:
            inp = input_map.get(item.key)
            resp = inp.response if inp else "no"
            val = _RESPONSE_VALUE.get(resp, 0.0)
            earned_pts = item.weight * val
            dim_earned += earned_pts
            evaluated += 1
            if resp in ("yes", "partial"):
                compliant += 1
            if resp == "no":
                gaps.append(item.label)
                if item.key in _RECOMMENDATIONS:
                    recommendations.append(_RECOMMENDATIONS[item.key])

        total_earned += dim_earned
        dim_score = round((dim_earned / dim_possible) * 100, 1) if dim_possible > 0 else 0.0
        dimension_scores.append(GovernanceDimensionScore(
            dimension=dim,
            label=_DIMENSION_LABELS.get(dim, dim),
            score=dim_score,
            earned=round(dim_earned, 2),
            possible=dim_possible,
            items_compliant=compliant,
            items_evaluated=evaluated,
        ))

    final_score = round((total_earned / total_possible) * 100, 1) if total_possible > 0 else 0.0
    return final_score, _level(final_score), dimension_scores, gaps, recommendations


def build_etapa6_memory(
    score: float,
    level: str,
    dimension_scores: list[GovernanceDimensionScore],
    gaps: list[str],
    answers: list[GovernanceItemInput] | None = None,
) -> dict:
    return {
        "governance": {
            "score": score,
            "level": level,
            "dimensions": [d.model_dump() for d in dimension_scores],
            "gaps": gaps,
            "answers": [
                {"key": a.key, "response": a.response.value if hasattr(a.response, "value") else a.response}
                for a in (answers or [])
            ],
        }
    }
