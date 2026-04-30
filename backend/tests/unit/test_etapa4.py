"""
Tests unitarios de Etapa 4 — motor de preguntas y generación de matrices.
"""
import pytest

from app.schemas.etapa4 import DiagnosticResponseInput
from app.services.ai.question_engine import (
    BASE_INTERNAL,
    EXTERNAL_QUESTIONS,
    build_question_set,
)
from app.services.ai.matrix_engine import build_mefi, build_mefe, build_swot, generate_matrices


def _buffer(is_family=False, priorities=None):
    if priorities is None:
        priorities = [
            {"challenge": "profitability",     "rank": 1, "activated_areas": ["finance"]},
            {"challenge": "commercial_growth",  "rank": 2, "activated_areas": ["commercial"]},
            {"challenge": "talent",             "rank": 3, "activated_areas": ["hr"]},
        ]
    return {
        "company": {"is_family_business": is_family},
        "priorities": priorities,
    }


def _responses(questions, default="yes"):
    return [DiagnosticResponseInput(question_id=q.question_id, response=default) for q in questions]


# ── Motor de preguntas ────────────────────────────────────────────────────────

def test_siempre_incluye_7_preguntas_base():
    questions = build_question_set(_buffer())
    base_ids = {q.question_id for q in BASE_INTERNAL}
    generated_ids = {q.question_id for q in questions}
    assert base_ids.issubset(generated_ids)


def test_siempre_incluye_5_preguntas_externas():
    questions = build_question_set(_buffer())
    external = [q for q in questions if q.is_external]
    assert len(external) == len(EXTERNAL_QUESTIONS)


def test_empresa_familiar_agrega_pregunta_base():
    q_sin = build_question_set(_buffer(is_family=False))
    q_con = build_question_set(_buffer(is_family=True))
    assert len(q_con) > len(q_sin)
    family_ids = {q.question_id for q in q_con if q.area == "family" and q.is_base}
    assert "base_familiar_1" in family_ids


def test_top3_prioridades_agregan_2_preguntas_cada_una():
    questions = build_question_set(_buffer())
    # finance (prioridad 1), commercial (prioridad 2), hr (prioridad 3)
    # cada una debe agregar 2 preguntas variables
    finance_var = [q for q in questions if q.area == "finance" and not q.is_base]
    commercial_var = [q for q in questions if q.area == "commercial" and not q.is_base]
    hr_var = [q for q in questions if q.area == "hr" and not q.is_base]
    assert len(finance_var) == 2
    assert len(commercial_var) == 2
    assert len(hr_var) == 2


def test_areas_no_prioritarias_tienen_cobertura_minima():
    questions = build_question_set(_buffer())
    # operations, strategy, legal no están en top 3 → deben tener al menos 1 pregunta
    for area in ["operations", "strategy", "legal"]:
        area_qs = [q for q in questions if q.area == area and not q.is_base and not q.is_external]
        assert len(area_qs) >= 1, f"Área {area} sin cobertura mínima"


def test_no_preguntas_duplicadas():
    questions = build_question_set(_buffer())
    ids = [q.question_id for q in questions]
    assert len(ids) == len(set(ids))


# ── Motor MEFI ────────────────────────────────────────────────────────────────

def test_mefi_yes_es_fortaleza():
    questions = build_question_set(_buffer())
    internal = [q for q in questions if not q.is_external]
    responses = {q.question_id: "yes" for q in internal}
    mefi = build_mefi(questions, responses, ["finance"])
    assert len(mefi["strengths"]) > 0
    assert len(mefi["weaknesses"]) == 0


def test_mefi_no_es_debilidad():
    questions = build_question_set(_buffer())
    internal = [q for q in questions if not q.is_external]
    responses = {q.question_id: "no" for q in internal}
    mefi = build_mefi(questions, responses, ["finance"])
    assert len(mefi["weaknesses"]) > 0
    assert len(mefi["strengths"]) == 0


def test_mefi_score_ponderado_correcto():
    questions = build_question_set(_buffer())
    internal = [q for q in questions if not q.is_external]
    responses = {q.question_id: "yes" for q in internal}
    mefi = build_mefi(questions, responses, ["finance"])
    for factor in mefi["strengths"]:
        expected = round(factor.weight * factor.rating, 3)
        assert factor.weighted_score == pytest.approx(expected, abs=0.001)


# ── Motor MEFE ────────────────────────────────────────────────────────────────

def test_mefe_competencia_yes_es_amenaza():
    questions = build_question_set(_buffer())
    external = [q for q in questions if q.is_external]
    responses = {q.question_id: "yes" for q in external}
    mefe = build_mefe(questions, responses)
    threat_areas = {f.area for f in mefe["threats"]}
    assert "competition" in threat_areas


def test_mefe_tecnologia_yes_es_oportunidad():
    questions = build_question_set(_buffer())
    external = [q for q in questions if q.is_external]
    responses = {q.question_id: "yes" for q in external}
    mefe = build_mefe(questions, responses)
    opp_areas = {f.area for f in mefe["opportunities"]}
    assert "technology" in opp_areas


# ── Business summary ──────────────────────────────────────────────────────────

def test_summary_menciona_conteos():
    questions = build_question_set(_buffer())
    responses = _responses(questions, "yes")
    matrices = generate_matrices(questions, responses, _buffer())
    assert str(matrices.strength_count) in matrices.business_summary


def test_summary_menciona_area_prioritaria():
    questions = build_question_set(_buffer())
    responses = _responses(questions, "partial")
    matrices = generate_matrices(questions, responses, _buffer())
    assert "finance" in matrices.business_summary


# ── FODA cruzado ─────────────────────────────────────────────────────────────

def test_swot_genera_las_4_estrategias():
    questions = build_question_set(_buffer())
    internal = [q for q in questions if not q.is_external]
    external = [q for q in questions if q.is_external]
    responses_int = {q.question_id: "yes" for q in internal[:3]}
    responses_int.update({q.question_id: "no" for q in internal[3:]})
    responses_ext = {q.question_id: "yes" for q in external}
    all_responses = {**responses_int, **responses_ext}

    mefi = build_mefi(questions, all_responses, ["finance"])
    mefe = build_mefe(questions, all_responses)
    swot = build_swot(mefi, mefe)

    assert len(swot.offensive) > 0
    assert len(swot.improvement) > 0
    assert len(swot.defensive) > 0
    assert len(swot.survival) > 0
