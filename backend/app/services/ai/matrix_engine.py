"""
Motor de matrices MEFI / MEFE / FODA — Etapa 4.
El usuario NUNCA ve matrices. Solo responde preguntas.
La IA genera conclusiones en lenguaje de negocio.
"""
from app.schemas.etapa4 import (
    DiagnosticMatrices,
    DiagnosticQuestion,
    DiagnosticResponseInput,
    MatrixFactor,
    SwotStrategies,
)

# Peso base por área (se incrementa si el área es prioridad Top 1-3)
_AREA_BASE_WEIGHT: dict[str, float] = {
    "strategy":   0.15,
    "commercial": 0.15,
    "operations": 0.12,
    "hr":         0.10,
    "finance":    0.15,
    "legal":      0.10,
    "family":     0.08,
}

# Áreas externas y su tendencia (amenaza vs oportunidad)
_EXTERNAL_THREAT_AREAS = {"competition", "regulation"}
_EXTERNAL_OPPORTUNITY_AREAS = {"technology", "social"}
_EXTERNAL_MIXED = {"economic"}


def _get_weight(area: str, priority_areas: list[str]) -> float:
    base = _AREA_BASE_WEIGHT.get(area, 0.10)
    # Aumentar peso si el área es top prioridad
    if area in priority_areas[:1]:
        return min(base + 0.05, 0.20)
    if area in priority_areas[:3]:
        return min(base + 0.02, 0.18)
    return base


def _response_to_rating(response: str, is_external: bool = False) -> int:
    """
    Interno: yes=4, partial=2, no=1
    Externo: yes=amenaza alta (rating 4), no=sin amenaza (rating 1)
    """
    mapping = {"yes": 4, "partial": 2, "no": 1, "unknown": 2}
    return mapping.get(response, 2)


def build_mefi(
    questions: list[DiagnosticQuestion],
    responses: dict[str, str],
    priority_areas: list[str],
) -> dict[str, list[MatrixFactor]]:
    strengths: list[MatrixFactor] = []
    weaknesses: list[MatrixFactor] = []

    for q in questions:
        if q.is_external:
            continue
        response = responses.get(q.question_id)
        if not response or response == "skipped":
            continue

        weight = _get_weight(q.area, priority_areas)
        rating = _response_to_rating(response)
        score = round(weight * rating, 3)
        factor = MatrixFactor(
            description=q.text, area=q.area,
            weight=weight, rating=rating, weighted_score=score,
        )
        if response == "yes":
            strengths.append(factor)
        else:
            weaknesses.append(factor)

    return {"strengths": strengths, "weaknesses": weaknesses}


def build_mefe(
    questions: list[DiagnosticQuestion],
    responses: dict[str, str],
) -> dict[str, list[MatrixFactor]]:
    opportunities: list[MatrixFactor] = []
    threats: list[MatrixFactor] = []

    for q in questions:
        if not q.is_external:
            continue
        response = responses.get(q.question_id)
        if not response or response == "skipped":
            continue

        weight = 0.20  # cada factor externo tiene peso igual
        rating = _response_to_rating(response, is_external=True)
        score = round(weight * rating, 3)
        factor = MatrixFactor(
            description=q.text, area=q.area,
            weight=weight, rating=rating, weighted_score=score,
        )

        # Clasificar según área y respuesta
        if q.area in _EXTERNAL_THREAT_AREAS:
            if response in ("yes", "partial"):
                threats.append(factor)
            else:
                opportunities.append(factor)
        elif q.area in _EXTERNAL_OPPORTUNITY_AREAS:
            if response in ("yes", "partial"):
                opportunities.append(factor)
            else:
                threats.append(factor)
        else:  # mixed (economic)
            if response == "yes":
                threats.append(factor)
            elif response == "partial":
                threats.append(factor)
            else:
                opportunities.append(factor)

    return {"opportunities": opportunities, "threats": threats}


def build_swot(
    mefi: dict[str, list[MatrixFactor]],
    mefe: dict[str, list[MatrixFactor]],
) -> SwotStrategies:
    strengths = mefi.get("strengths", [])
    weaknesses = mefi.get("weaknesses", [])
    opportunities = mefe.get("opportunities", [])
    threats = mefe.get("threats", [])

    offensive: list[str] = []      # F+O
    improvement: list[str] = []    # D+O
    defensive: list[str] = []      # F+A
    survival: list[str] = []       # D+A

    # F+O: usar fortalezas para aprovechar oportunidades
    for s in strengths[:2]:
        for o in opportunities[:2]:
            offensive.append(
                f"Aprovechar '{s.description[:40]}...' para capitalizar '{o.description[:40]}...'"
            )

    # D+O: superar debilidades aprovechando oportunidades
    for w in weaknesses[:2]:
        for o in opportunities[:1]:
            improvement.append(
                f"Mejorar '{w.description[:40]}...' para aprovechar '{o.description[:40]}...'"
            )

    # F+A: usar fortalezas para mitigar amenazas
    for s in strengths[:1]:
        for t in threats[:2]:
            defensive.append(
                f"Usar '{s.description[:40]}...' para enfrentar '{t.description[:40]}...'"
            )

    # D+A: reducir debilidades para evitar amenazas
    for w in weaknesses[:1]:
        for t in threats[:1]:
            survival.append(
                f"Resolver '{w.description[:40]}...' antes de que '{t.description[:40]}...' impacte más"
            )

    return SwotStrategies(
        offensive=offensive or ["Identificar nuevas oportunidades de crecimiento basadas en fortalezas actuales"],
        improvement=improvement or ["Fortalecer áreas débiles para estar listos ante oportunidades"],
        defensive=defensive or ["Mantener fortalezas actuales como escudo ante amenazas del entorno"],
        survival=survival or ["Atender debilidades críticas de forma urgente"],
    )


def build_business_summary(
    mefi: dict[str, list[MatrixFactor]],
    mefe: dict[str, list[MatrixFactor]],
    priority_areas: list[str],
) -> str:
    s_count = len(mefi.get("strengths", []))
    w_count = len(mefi.get("weaknesses", []))
    o_count = len(mefe.get("opportunities", []))
    t_count = len(mefe.get("threats", []))

    urgency = ""
    if w_count > s_count:
        urgency = " Las áreas de mejora superan las fortalezas — se recomienda atención prioritaria."
    elif s_count >= 5:
        urgency = " La empresa muestra una base sólida para crecer."

    top_area = priority_areas[0] if priority_areas else "estrategia"

    return (
        f"Tienes {s_count} fortaleza{'s' if s_count != 1 else ''} clara{'s' if s_count != 1 else ''}, "
        f"{w_count} área{'s' if w_count != 1 else ''} de mejora, "
        f"{o_count} oportunidad{'es' if o_count != 1 else ''} identificada{'s' if o_count != 1 else ''} "
        f"y {t_count} amenaza{'s' if t_count != 1 else ''} en el entorno. "
        f"El área más urgente según tus prioridades es {top_area}.{urgency}"
    )


def generate_matrices(
    questions: list[DiagnosticQuestion],
    responses_input: list[DiagnosticResponseInput],
    memory_buffer: dict,
) -> DiagnosticMatrices:
    # Construir dict de respuestas para acceso O(1)
    responses = {r.question_id: r.response for r in responses_input}

    # Áreas prioritarias desde el memory buffer
    priority_areas = [
        p.get("activated_areas", [{}])[0] if p.get("activated_areas") else ""
        for p in sorted(memory_buffer.get("priorities", []), key=lambda p: p.get("rank", 99))
    ]

    mefi = build_mefi(questions, responses, priority_areas)
    mefe = build_mefe(questions, responses)
    swot = build_swot(mefi, mefe)
    summary = build_business_summary(mefi, mefe, priority_areas)

    return DiagnosticMatrices(
        mefi=mefi,
        mefe=mefe,
        swot=swot,
        business_summary=summary,
        strength_count=len(mefi.get("strengths", [])),
        weakness_count=len(mefi.get("weaknesses", [])),
    )


_AREA_LABELS: dict[str, str] = {
    "strategy":    "Estrategia",
    "commercial":  "Comercial",
    "operations":  "Operaciones",
    "hr":          "Capital Humano",
    "finance":     "Finanzas",
    "legal":       "Legal",
    "family":      "Empresa Familiar",
    "competition": "Competencia",
    "technology":  "Tecnología",
    "regulation":  "Regulación",
    "economic":    "Entorno Económico",
    "social":      "Entorno Social",
}


def _build_area_completion(
    questions: list[DiagnosticQuestion],
    responses: dict[str, str],
) -> dict:
    areas: dict[str, dict] = {}
    for q in questions:
        area = q.area
        if area not in areas:
            areas[area] = {
                "label": _AREA_LABELS.get(area, area.title()),
                "is_external": q.is_external,
                "total": 0,
                "answered": 0,
                "skipped": 0,
                "questions": [],
            }
        response = responses.get(q.question_id, "skipped")
        areas[area]["total"] += 1
        if response == "skipped":
            areas[area]["skipped"] += 1
        else:
            areas[area]["answered"] += 1
        areas[area]["questions"].append({
            "question_id": q.question_id,
            "text": q.text,
            "response": response,
        })

    for data in areas.values():
        total = data["total"]
        data["pct"] = round(data["answered"] / total * 100) if total else 0

    return areas


def build_etapa4_memory(
    questions: list[DiagnosticQuestion],
    responses_input: list[DiagnosticResponseInput],
    matrices: DiagnosticMatrices,
) -> dict:
    responses = {r.question_id: r.response for r in responses_input}
    return {
        "diagnostic_responses": [
            {
                "question_id": r.question_id,
                "response": r.response,
                "area": next((q.area for q in questions if q.question_id == r.question_id), "unknown"),
                "is_external": next((q.is_external for q in questions if q.question_id == r.question_id), False),
            }
            for r in responses_input
        ],
        "diagnostic_area_completion": _build_area_completion(questions, responses),
        "matrices": {
            "mefi": {
                "strengths": [f.model_dump() for f in matrices.mefi.get("strengths", [])],
                "weaknesses": [f.model_dump() for f in matrices.mefi.get("weaknesses", [])],
            },
            "mefe": {
                "opportunities": [f.model_dump() for f in matrices.mefe.get("opportunities", [])],
                "threats": [f.model_dump() for f in matrices.mefe.get("threats", [])],
            },
            "swot": matrices.swot.model_dump(),
            "business_summary": matrices.business_summary,
        },
    }
