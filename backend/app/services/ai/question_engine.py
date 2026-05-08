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
        description="Evalúa si el equipo directivo tiene alineación sobre el rumbo futuro de la empresa.",
        response_options=YES_PARTIAL_NO,
    ),
    DiagnosticQuestion(
        question_id="base_estrategia_2", area="strategy", is_base=True,
        text="Tenemos planeación estratégica, misión y visión definidas",
        description="Verifica la existencia de documentos formales que guíen la toma de decisiones estratégicas.",
        response_options=YES_PARTIAL_NO,
    ),
    DiagnosticQuestion(
        question_id="base_comercial_1", area="commercial", is_base=True,
        text="Sé quiénes son mis mejores clientes y por qué me compran",
        description="Mide el conocimiento del mercado y la propuesta de valor hacia los clientes actuales.",
        response_options=YES_PARTIAL_NO,
    ),
    DiagnosticQuestion(
        question_id="base_operativo_1", area="operations", is_base=True,
        text="Nuestros procesos principales están documentados",
        description="Evalúa si los procesos clave están escritos y son replicables por cualquier colaborador.",
        response_options=YES_PARTIAL_NO,
    ),
    DiagnosticQuestion(
        question_id="base_rh_1", area="hr", is_base=True,
        text="Tenemos claridad de funciones y perfiles de puesto",
        description="Verifica si cada persona en la empresa conoce sus responsabilidades y lo que se espera de ella.",
        response_options=YES_PARTIAL_NO,
    ),
    DiagnosticQuestion(
        question_id="base_financiero_1", area="finance", is_base=True,
        text="Revisamos estado de resultados y tomamos decisiones con esa información",
        description="Mide si la empresa usa información financiera para tomar decisiones, no solo para cumplir obligaciones fiscales.",
        response_options=YES_PARTIAL_NO,
    ),
    DiagnosticQuestion(
        question_id="base_legal_1", area="legal", is_base=True,
        text="Estamos al corriente en obligaciones fiscales y sin litigios pendientes",
        description="Evalúa el estado de cumplimiento fiscal y la ausencia de contingencias legales activas.",
        response_options=YES_PARTIAL_NO,
    ),
]

# Pregunta familiar condicional
FAMILY_QUESTION = DiagnosticQuestion(
    question_id="base_familiar_1", area="family", is_base=True, is_conditional=True,
    text="Las responsabilidades de familiares en la empresa están claramente definidas",
    description="Verifica si los familiares que trabajan en la empresa tienen roles definidos, evitando conflictos de autoridad.",
    response_options=YES_PARTIAL_NO,
)

# ── Banco de preguntas variables por área ─────────────────────────────────────

QUESTION_BANK: dict[str, list[DiagnosticQuestion]] = {
    "finance": [
        DiagnosticQuestion(question_id="fin_1", area="finance",
            text="Tenemos control claro de nuestros costos",
            description="Evalúa si la empresa sabe cuánto cuesta producir o entregar cada producto o servicio.",
            response_options=YES_PARTIAL_NO),
        DiagnosticQuestion(question_id="fin_2", area="finance",
            text="Conocemos nuestros márgenes por producto o servicio",
            description="Mide el conocimiento de rentabilidad por línea de negocio o producto.",
            response_options=YES_PARTIAL_NO),
        DiagnosticQuestion(question_id="fin_3", area="finance",
            text="Damos seguimiento a flujo de efectivo",
            description="Verifica si hay un proceso regular de revisión del dinero disponible y proyectado.",
            response_options=YES_PARTIAL_NO),
    ],
    "commercial": [
        DiagnosticQuestion(question_id="com_1", area="commercial",
            text="Tenemos un proceso claro para generar nuevos clientes",
            description="Evalúa si existe un proceso documentado y repetible para captar clientes.",
            response_options=YES_PARTIAL_NO),
        DiagnosticQuestion(question_id="com_2", area="commercial",
            text="No dependemos de pocos clientes",
            description="Mide la concentración de clientes — alta dependencia implica riesgo comercial elevado.",
            response_options=YES_PARTIAL_NO),
        DiagnosticQuestion(question_id="com_3", area="commercial",
            text="Conocemos a nuestra competencia",
            description="Verifica si la empresa monitorea activamente a sus competidores y su posicionamiento.",
            response_options=YES_PARTIAL_NO),
    ],
    "operations": [
        DiagnosticQuestion(question_id="ops_1", area="operations",
            text="Nuestros procesos están estandarizados",
            description="Evalúa si los procesos producen el mismo resultado independientemente de quién los ejecuta.",
            response_options=YES_PARTIAL_NO),
        DiagnosticQuestion(question_id="ops_2", area="operations",
            text="Medimos eficiencia operativa",
            description="Verifica si la empresa mide indicadores operativos clave como tiempos, capacidad y productividad.",
            response_options=YES_PARTIAL_NO),
        DiagnosticQuestion(question_id="ops_3", area="operations",
            text="Tenemos control de calidad",
            description="Mide la existencia de mecanismos para detectar y corregir errores antes de llegar al cliente.",
            response_options=YES_PARTIAL_NO),
    ],
    "hr": [
        DiagnosticQuestion(question_id="rh_1", area="hr",
            text="Evaluamos el desempeño del equipo",
            description="Evalúa si hay un sistema formal o informal de evaluación de desempeño para el equipo.",
            response_options=YES_PARTIAL_NO),
        DiagnosticQuestion(question_id="rh_2", area="hr",
            text="Tenemos estructura organizacional clara",
            description="Verifica si el organigrama es claro y cada área tiene responsabilidades definidas.",
            response_options=YES_PARTIAL_NO),
        DiagnosticQuestion(question_id="rh_3", area="hr",
            text="Podemos delegar responsabilidades",
            description="Mide si los directivos pueden asignar tareas con confianza sin supervisar cada detalle.",
            response_options=YES_PARTIAL_NO),
    ],
    "strategy": [
        DiagnosticQuestion(question_id="est_1", area="strategy",
            text="Tenemos objetivos claros a mediano plazo",
            description="Verifica la existencia de objetivos concretos y medibles para los próximos 1-3 años.",
            response_options=YES_PARTIAL_NO),
        DiagnosticQuestion(question_id="est_2", area="strategy",
            text="Damos seguimiento al plan estratégico",
            description="Evalúa si hay revisiones periódicas del avance del plan estratégico.",
            response_options=YES_PARTIAL_NO),
    ],
    "legal": [
        DiagnosticQuestion(question_id="leg_1", area="legal",
            text="Tenemos documentación legal actualizada",
            description="Evalúa el estado de la documentación corporativa: actas, poderes y contratos vigentes.",
            response_options=YES_PARTIAL_NO),
        DiagnosticQuestion(question_id="leg_2", area="legal",
            text="Contamos con contratos formales con clientes, proveedores y empleados",
            description="Verifica si las relaciones comerciales con terceros están formalizadas mediante contratos.",
            response_options=YES_PARTIAL_NO),
    ],
    "family": [
        DiagnosticQuestion(question_id="fam_1", area="family",
            text="Existe claridad en roles familiares",
            description="Evalúa si los miembros de la familia tienen títulos, funciones y jerarquía claramente diferenciados.",
            response_options=YES_PARTIAL_NO),
        DiagnosticQuestion(question_id="fam_2", area="family",
            text="Se tiene claro el proceso de sucesión",
            description="Verifica si existe un plan documentado para la transferencia de liderazgo o propiedad.",
            response_options=YES_PARTIAL_NO),
        DiagnosticQuestion(question_id="fam_3", area="family",
            text="Hay acuerdos entre socios",
            description="Evalúa si existe un pacto de socios o acuerdo familiar que regule las decisiones importantes.",
            response_options=YES_PARTIAL_NO),
        DiagnosticQuestion(question_id="fam_4", area="family",
            text="Las finanzas de la empresa están separadas de las personales o familiares",
            description="Mide si las finanzas personales de la familia y las de la empresa están claramente separadas.",
            response_options=YES_PARTIAL_NO),
    ],
}

# ── Preguntas externas (siempre aparecen) ─────────────────────────────────────

EXTERNAL_QUESTIONS: list[DiagnosticQuestion] = [
    DiagnosticQuestion(
        question_id="ext_competencia", area="competition", is_external=True,
        text="Hay nuevos competidores entrando a mi mercado",
        description="Identifica si hay nuevos actores que puedan afectar la participación de mercado de la empresa.",
        response_options=YES_NO_UNKNOWN,
    ),
    DiagnosticQuestion(
        question_id="ext_tecnologia", area="technology", is_external=True,
        text="La tecnología está cambiando cómo operamos",
        description="Evalúa si la adopción o no de nuevas tecnologías representa una ventaja o riesgo competitivo.",
        response_options=YES_NO_UNKNOWN,
    ),
    DiagnosticQuestion(
        question_id="ext_regulacion", area="regulation", is_external=True,
        text="La regulación de mi industria se está volviendo más exigente",
        description="Verifica el impacto del entorno regulatorio en los costos operativos o la forma de operar.",
        response_options=YES_NO_UNKNOWN,
    ),
    DiagnosticQuestion(
        question_id="ext_economico", area="economic", is_external=True,
        text="Factores económicos (costos, inflación, tipo de cambio) afectan mi negocio",
        description="Mide la exposición de la empresa a variables macroeconómicas fuera de su control.",
        response_options=YES_PARTIAL_NO,
    ),
    DiagnosticQuestion(
        question_id="ext_social", area="social", is_external=True,
        text="Las expectativas de mis clientes están cambiando (nuevos hábitos, canales, exigencias)",
        description="Evalúa si los cambios en el comportamiento del consumidor están afectando la demanda o el modelo de negocio.",
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
