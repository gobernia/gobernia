"""
Motor de preguntas dinámicas — Etapa 4.
Genera el set personalizado de preguntas según los datos de Etapas 1-3.
Implementa exactamente las reglas del spec:
  - 7 preguntas base internas (siempre)
  - +1 familiar si empresa familiar
  - +2 por cada área en Top 3 prioridades
  - +1 por cada área NO en prioridades (cobertura mínima)
  - 5 preguntas externas (siempre)
"""
from app.schemas.etapa4 import DiagnosticQuestion

YES_PARTIAL_NO = ["yes", "partial", "no"]
YES_NO_UNKNOWN = ["yes", "no", "unknown"]
YES_PARTIAL_NO_U = ["yes", "partial", "no", "unknown"]

# ── Banco de preguntas internas base (siempre aparecen) ───────────────────────

BASE_INTERNAL: list[DiagnosticQuestion] = [
    DiagnosticQuestion(
        question_id="base_estrategia_1", area="strategy", is_base=True,
        text="Tengo claro hacia dónde va mi empresa en los próximos años",
        response_options=YES_PARTIAL_NO,
    ),
    DiagnosticQuestion(
        question_id="base_estrategia_2", area="strategy", is_base=True,
        text="Tenemos planeación estratégica, misión y visión definidas",
        response_options=YES_PARTIAL_NO,
    ),
    DiagnosticQuestion(
        question_id="base_comercial_1", area="commercial", is_base=True,
        text="Sé quiénes son mis mejores clientes y por qué me compran",
        response_options=YES_PARTIAL_NO,
    ),
    DiagnosticQuestion(
        question_id="base_operativo_1", area="operations", is_base=True,
        text="Nuestros procesos principales están documentados",
        response_options=YES_PARTIAL_NO,
    ),
    DiagnosticQuestion(
        question_id="base_rh_1", area="hr", is_base=True,
        text="Tenemos claridad de funciones y perfiles de puesto",
        response_options=YES_PARTIAL_NO,
    ),
    DiagnosticQuestion(
        question_id="base_financiero_1", area="finance", is_base=True,
        text="Revisamos estado de resultados y tomamos decisiones con esa información",
        response_options=YES_PARTIAL_NO,
    ),
    DiagnosticQuestion(
        question_id="base_legal_1", area="legal", is_base=True,
        text="Estamos al corriente en obligaciones fiscales y sin litigios pendientes",
        response_options=YES_PARTIAL_NO,
    ),
]

# Pregunta familiar condicional
FAMILY_QUESTION = DiagnosticQuestion(
    question_id="base_familiar_1", area="family", is_base=True, is_conditional=True,
    text="Las responsabilidades de familiares en la empresa están claramente definidas",
    response_options=YES_PARTIAL_NO,
)

# ── Banco de preguntas variables por área ─────────────────────────────────────

QUESTION_BANK: dict[str, list[DiagnosticQuestion]] = {
    "finance": [
        DiagnosticQuestion(question_id="fin_1", area="finance",
            text="Tenemos control claro de nuestros costos", response_options=YES_PARTIAL_NO),
        DiagnosticQuestion(question_id="fin_2", area="finance",
            text="Conocemos nuestros márgenes por producto o servicio", response_options=YES_PARTIAL_NO),
        DiagnosticQuestion(question_id="fin_3", area="finance",
            text="Damos seguimiento a flujo de efectivo", response_options=YES_PARTIAL_NO),
    ],
    "commercial": [
        DiagnosticQuestion(question_id="com_1", area="commercial",
            text="Tenemos un proceso claro para generar nuevos clientes", response_options=YES_PARTIAL_NO),
        DiagnosticQuestion(question_id="com_2", area="commercial",
            text="No dependemos de pocos clientes", response_options=YES_PARTIAL_NO),
        DiagnosticQuestion(question_id="com_3", area="commercial",
            text="Conocemos a nuestra competencia", response_options=YES_PARTIAL_NO),
    ],
    "operations": [
        DiagnosticQuestion(question_id="ops_1", area="operations",
            text="Nuestros procesos están estandarizados", response_options=YES_PARTIAL_NO),
        DiagnosticQuestion(question_id="ops_2", area="operations",
            text="Medimos eficiencia operativa", response_options=YES_PARTIAL_NO),
        DiagnosticQuestion(question_id="ops_3", area="operations",
            text="Tenemos control de calidad", response_options=YES_PARTIAL_NO),
    ],
    "hr": [
        DiagnosticQuestion(question_id="rh_1", area="hr",
            text="Evaluamos el desempeño del equipo", response_options=YES_PARTIAL_NO),
        DiagnosticQuestion(question_id="rh_2", area="hr",
            text="Tenemos estructura organizacional clara", response_options=YES_PARTIAL_NO),
        DiagnosticQuestion(question_id="rh_3", area="hr",
            text="Podemos delegar responsabilidades", response_options=YES_PARTIAL_NO),
    ],
    "strategy": [
        DiagnosticQuestion(question_id="est_1", area="strategy",
            text="Tenemos objetivos claros a mediano plazo", response_options=YES_PARTIAL_NO),
        DiagnosticQuestion(question_id="est_2", area="strategy",
            text="Damos seguimiento al plan estratégico", response_options=YES_PARTIAL_NO),
    ],
    "legal": [
        DiagnosticQuestion(question_id="leg_1", area="legal",
            text="Tenemos documentación legal actualizada", response_options=YES_PARTIAL_NO),
        DiagnosticQuestion(question_id="leg_2", area="legal",
            text="Contamos con contratos formales con clientes, proveedores y empleados",
            response_options=YES_PARTIAL_NO),
    ],
    "family": [
        DiagnosticQuestion(question_id="fam_1", area="family",
            text="Existe claridad en roles familiares", response_options=YES_PARTIAL_NO),
        DiagnosticQuestion(question_id="fam_2", area="family",
            text="Se tiene claro el proceso de sucesión", response_options=YES_PARTIAL_NO),
        DiagnosticQuestion(question_id="fam_3", area="family",
            text="Hay acuerdos entre socios", response_options=YES_PARTIAL_NO),
        DiagnosticQuestion(question_id="fam_4", area="family",
            text="Las finanzas de la empresa están separadas de las personales o familiares",
            response_options=YES_PARTIAL_NO),
    ],
}

# ── Preguntas externas (siempre aparecen) ─────────────────────────────────────

EXTERNAL_QUESTIONS: list[DiagnosticQuestion] = [
    DiagnosticQuestion(
        question_id="ext_competencia", area="competition", is_external=True,
        text="Hay nuevos competidores entrando a mi mercado",
        response_options=YES_NO_UNKNOWN,
    ),
    DiagnosticQuestion(
        question_id="ext_tecnologia", area="technology", is_external=True,
        text="La tecnología está cambiando cómo operamos",
        response_options=YES_NO_UNKNOWN,
    ),
    DiagnosticQuestion(
        question_id="ext_regulacion", area="regulation", is_external=True,
        text="La regulación de mi industria se está volviendo más exigente",
        response_options=YES_NO_UNKNOWN,
    ),
    DiagnosticQuestion(
        question_id="ext_economico", area="economic", is_external=True,
        text="Factores económicos (costos, inflación, tipo de cambio) afectan mi negocio",
        response_options=YES_PARTIAL_NO,
    ),
    DiagnosticQuestion(
        question_id="ext_social", area="social", is_external=True,
        text="Las expectativas de mis clientes están cambiando (nuevos hábitos, canales, exigencias)",
        response_options=YES_PARTIAL_NO,
    ),
]

# ── Mapeo ChallengeType → área principal para selección de preguntas ──────────

_CHALLENGE_TO_AREA: dict[str, str] = {
    "profitability":          "finance",
    "commercial_growth":      "commercial",
    "talent":                 "hr",
    "operations":             "operations",
    "organizational_clarity": "hr",
    "delegation_succession":  "family",
    "market_position":        "commercial",
    "compliance_risk":        "legal",
    "innovation_technology":  "operations",
    "other":                  "strategy",
}

_ALL_VARIABLE_AREAS = {"finance", "commercial", "operations", "hr", "strategy", "legal"}


def build_question_set(memory_buffer: dict) -> list[DiagnosticQuestion]:
    """
    Construye el set personalizado de preguntas para Etapa 4.
    Reglas del spec:
      - Top 1, 2, 3 → +2 preguntas de su área
      - Áreas no seleccionadas → +1 pregunta (cobertura mínima)
    """
    is_family = memory_buffer.get("company", {}).get("is_family_business", False)
    priorities = memory_buffer.get("priorities", [])

    # 1. Base internas
    questions: list[DiagnosticQuestion] = list(BASE_INTERNAL)

    # 2. Pregunta familiar condicional
    if is_family:
        questions.append(FAMILY_QUESTION)

    # 3. Preguntas variables por prioridad
    used_ids: set[str] = {q.question_id for q in questions}
    top3_areas: list[str] = []

    sorted_priorities = sorted(priorities, key=lambda p: p.get("rank", 99))
    for p in sorted_priorities[:3]:
        area = _CHALLENGE_TO_AREA.get(p.get("challenge", ""), "strategy")
        top3_areas.append(area)
        bank = QUESTION_BANK.get(area, [])
        added = 0
        for q in bank:
            if q.question_id not in used_ids and added < 2:
                questions.append(q)
                used_ids.add(q.question_id)
                added += 1

    # 4. Cobertura mínima para áreas no prioritarias
    covered_areas = set(top3_areas)
    for area in _ALL_VARIABLE_AREAS - covered_areas:
        bank = QUESTION_BANK.get(area, [])
        for q in bank:
            if q.question_id not in used_ids:
                questions.append(q)
                used_ids.add(q.question_id)
                break

    # 5. Preguntas externas
    questions.extend(EXTERNAL_QUESTIONS)

    return questions
