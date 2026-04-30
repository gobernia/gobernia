"""
Tests unitarios de Etapa 6 — motor de gobierno y cálculo de Governance Score.
"""
import pytest

from app.schemas.etapa6 import GovernanceItemInput
from app.services.ai.governance_engine import (
    build_governance_items,
    calculate_governance_score,
    _CORE_WEIGHT_TOTAL,
    _FAMILY_WEIGHT_TOTAL,
    _ALL_ITEMS,
)


def _buf(is_family=False):
    return {"company": {"is_family_business": is_family}}


def _responses(items, default="yes"):
    return [GovernanceItemInput(key=i.key, response=default) for i in items]


# ── Filtrado de ítems ─────────────────────────────────────────────────────────

def test_no_familiar_no_incluye_items_familia():
    items = build_governance_items(_buf(is_family=False))
    assert all(not i.is_conditional for i in items)


def test_familiar_incluye_items_familia():
    items = build_governance_items(_buf(is_family=True))
    family_keys = {i.key for i in items if i.is_conditional}
    assert "has_family_protocol" in family_keys
    assert "has_succession_plan" in family_keys
    assert "has_conflict_resolution" in family_keys


def test_no_familiar_tiene_10_items():
    items = build_governance_items(_buf(is_family=False))
    assert len(items) == 10


def test_familiar_tiene_13_items():
    items = build_governance_items(_buf(is_family=True))
    assert len(items) == 13


def test_pesos_core_suman_85():
    assert _CORE_WEIGHT_TOTAL == 85


def test_pesos_familia_suman_15():
    assert _FAMILY_WEIGHT_TOTAL == 15


# ── Score total ───────────────────────────────────────────────────────────────

def test_todos_yes_no_familiar_score_100():
    items = build_governance_items(_buf(is_family=False))
    inp = _responses(items, "yes")
    score, level, _, gaps, _ = calculate_governance_score(items, inp)
    assert score == 100.0
    assert level == "Excelente"
    assert len(gaps) == 0


def test_todos_yes_familiar_score_100():
    items = build_governance_items(_buf(is_family=True))
    inp = _responses(items, "yes")
    score, level, _, gaps, _ = calculate_governance_score(items, inp)
    assert score == 100.0
    assert level == "Excelente"


def test_todos_no_score_0():
    items = build_governance_items(_buf(is_family=False))
    inp = _responses(items, "no")
    score, level, _, gaps, _ = calculate_governance_score(items, inp)
    assert score == 0.0
    assert level == "Inicial"
    assert len(gaps) == 10


def test_partial_score_es_50():
    items = build_governance_items(_buf(is_family=False))
    inp = _responses(items, "partial")
    score, _, _, _, _ = calculate_governance_score(items, inp)
    assert score == 50.0


# ── Niveles ───────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("pct,expected_level", [
    (0.0,  "Inicial"),
    (40.0, "Inicial"),
    (41.0, "En desarrollo"),
    (65.0, "En desarrollo"),
    (66.0, "Consolidado"),
    (85.0, "Consolidado"),
    (86.0, "Excelente"),
    (100.0, "Excelente"),
])
def test_niveles(pct, expected_level):
    items = build_governance_items(_buf(is_family=False))
    # Construir respuestas que dan el porcentaje exacto
    # yes=weight completo → necesitamos earned = pct/100 * 85
    # Usamos partial (50%) en todo si pct~50, o mezcla yes/no
    # Para simplicidad: si pct == 0 → todos no, pct == 50 → partial, pct == 100 → yes
    # Para otros valores: verificamos solo level con score sintético
    from app.services.ai.governance_engine import _level
    assert _level(pct) == expected_level


# ── Dimension scores ──────────────────────────────────────────────────────────

def test_dimension_scores_incluye_board():
    items = build_governance_items(_buf(is_family=False))
    inp = _responses(items, "yes")
    _, _, dim_scores, _, _ = calculate_governance_score(items, inp)
    dims = {d.dimension for d in dim_scores}
    assert "board" in dims
    assert "compliance" in dims
    assert "documentation" in dims


def test_dimension_board_max_40pts():
    items = build_governance_items(_buf(is_family=False))
    board_items = [i for i in items if i.dimension == "board"]
    assert sum(i.weight for i in board_items) == 40


def test_dimension_score_correcta_board():
    items = build_governance_items(_buf(is_family=False))
    # Solo responder board con yes, resto no
    inp = [
        GovernanceItemInput(key=i.key, response="yes" if i.dimension == "board" else "no")
        for i in items
    ]
    _, _, dim_scores, _, _ = calculate_governance_score(items, inp)
    board_score = next(d for d in dim_scores if d.dimension == "board")
    assert board_score.score == 100.0


# ── Gaps y recomendaciones ────────────────────────────────────────────────────

def test_gaps_contiene_labels_no():
    items = build_governance_items(_buf(is_family=False))
    inp = [
        GovernanceItemInput(key=i.key, response="no" if i.key == "has_formal_board" else "yes")
        for i in items
    ]
    _, _, _, gaps, recs = calculate_governance_score(items, inp)
    assert any("Consejo" in g for g in gaps)
    assert any("consejo" in r.lower() or "formalizar" in r.lower() for r in recs)


def test_na_no_genera_gap():
    items = build_governance_items(_buf(is_family=False))
    inp = [
        GovernanceItemInput(key=i.key, response="na" if i.key == "has_financial_audit" else "yes")
        for i in items
    ]
    _, _, _, gaps, _ = calculate_governance_score(items, inp)
    # "na" no cuenta como gap (brecha), solo como 0 puntos
    audit_item = next(i for i in items if i.key == "has_financial_audit")
    assert audit_item.label not in gaps


def test_familiar_gaps_incluyen_protocolo_cuando_no():
    items = build_governance_items(_buf(is_family=True))
    inp = [
        GovernanceItemInput(key=i.key, response="no" if i.key == "has_family_protocol" else "yes")
        for i in items
    ]
    _, _, _, gaps, recs = calculate_governance_score(items, inp)
    assert any("protocolo" in g.lower() or "Protocolo" in g for g in gaps)
    assert any("protocolo" in r.lower() for r in recs)
