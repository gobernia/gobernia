"""
Base del agente IA — construye el prompt del sistema y llama a Claude.
Cada agente (CFO, CSO, CRO, Auditor) hereda de aquí.
"""
import json
import logging
import time
from typing import AsyncIterator

import anthropic

from app.core.config import settings
from app.schemas.board_session import normalize_analysis
from app.services.ai.doc_blocks import build_doc_blocks
from app.services.ai.knowledge_base import build_knowledge_for_agent

_log = logging.getLogger(__name__)

# Errores transitorios que vale la pena reintentar.
_RETRYABLE = (
    anthropic.RateLimitError,
    anthropic.APITimeoutError,
    anthropic.APIConnectionError,
    anthropic.InternalServerError,
)

# Esperas en segundos entre intentos (4 intentos = inmediato + 3 retries)
_RETRY_DELAYS = (0, 5, 15, 45)


def _create_with_retry(client: anthropic.Anthropic, **kwargs):
    """
    Llama a client.messages.create con backoff exponencial en errores
    transitorios (429 rate limit, 5xx, timeouts de red).
    Tras agotar los reintentos, re-lanza la excepción.
    """
    last_exc: Exception | None = None
    for attempt, delay in enumerate(_RETRY_DELAYS):
        if delay > 0:
            _log.warning(
                "anthropic transient error (%s); retry %d/%d en %ds",
                type(last_exc).__name__ if last_exc else "?",
                attempt, len(_RETRY_DELAYS) - 1, delay,
            )
            time.sleep(delay)
        try:
            return client.messages.create(**kwargs)
        except _RETRYABLE as e:
            last_exc = e
    assert last_exc is not None
    raise last_exc


def _stream_with_retry(client: anthropic.Anthropic, **kwargs):
    """Igual que _create_with_retry pero usando streaming (client.messages.stream).
    El streaming mantiene viva la conexión con eventos ping durante operaciones largas
    (p.ej. web_search), evitando APITimeoutError en requests largos. Devuelve el Message final.
    """
    last_exc: Exception | None = None
    for attempt, delay in enumerate(_RETRY_DELAYS):
        if delay > 0:
            _log.warning(
                "anthropic transient error (%s); stream-retry %d/%d en %ds",
                type(last_exc).__name__ if last_exc else "?",
                attempt, len(_RETRY_DELAYS) - 1, delay,
            )
            time.sleep(delay)
        try:
            with client.messages.stream(**kwargs) as stream:
                return stream.get_final_message()
        except _RETRYABLE as e:
            last_exc = e
    assert last_exc is not None
    raise last_exc

VALID_AGENTS = {"CFO", "CSO", "CRO", "Auditor"}

_MONTH_NAMES = [
    "", "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
    "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre",
]


def _period_label(year: int, month: int) -> str:
    return f"{_MONTH_NAMES[month]} {year}"


def _get_agent_config(memory_buffer: dict, agent: str) -> dict:
    return memory_buffer.get("agent_configs", {}).get(agent, {})


def _build_company_context(memory_buffer: dict) -> str:
    company = memory_buffer.get("company", {})
    vision = memory_buffer.get("vision", {})
    narrative = memory_buffer.get("ai_context", {}).get("company_narrative", "")
    governance = memory_buffer.get("governance", {})

    parts = [narrative] if narrative else []

    if company:
        details = []
        if company.get("industry"):
            details.append(f"Industria: {company['industry']}")
        if company.get("employees"):
            details.append(f"Empleados: {company['employees']}")
        if company.get("annual_revenue"):
            details.append(f"Ingresos anuales: {company['annual_revenue']} USD")
        if company.get("years_operating"):
            details.append(f"Años de operación: {company['years_operating']}")
        if company.get("has_board"):
            details.append(f"Consejo formal: {company['has_board']}")
        if details:
            parts.append("DATOS DE LA EMPRESA: " + " | ".join(details))

    if vision.get("statement"):
        parts.append(f"VISIÓN: {vision['statement']}")
    if governance.get("score"):
        parts.append(
            f"GOVERNANCE SCORE: {governance['score']}/100 ({governance.get('level', '')})"
        )
    return "\n".join(parts)


def _build_kpi_context(kpi_snapshot: dict | None, memory_buffer: dict | None = None) -> str:
    if not kpi_snapshot and memory_buffer:
        kpi_snapshot = memory_buffer.get("kpis")
    if not kpi_snapshot:
        return "KPIs del periodo: No ingresados aún."
    lines = ["KPIs DEL PERIODO:"]
    for dimension, kpis in kpi_snapshot.items():
        lines.append(f"\n  {dimension.upper()}:")
        for kpi in kpis:
            val = kpi.get("current_value")
            bench = kpi.get("benchmark")
            alert = kpi.get("alert", "")
            status = ""
            if val is not None and bench is not None:
                status = " ⚠️ ALERTA" if alert else " ✓"
            val_str = str(val) if val is not None else "No reportado"
            lines.append(
                f"    - {kpi['label']}: {val_str} {kpi.get('unit','')} "
                f"(benchmark: {bench}){status}"
            )
    return "\n".join(lines)


_ANIOS = ("anio1", "anio2", "anio3")

SIN_ROADMAP = (
    "ROADMAP ESTRATÉGICO: El dueño aún no ha validado su Roadmap Estratégico. "
    "No existe un plan rector que puedas leer: NO inventes pilares, metas ni milestones, "
    "y no te refieras al roadmap como si lo hubieras visto. Analiza con el contexto, los KPIs y "
    "los documentos, y si el juicio depende del plan de largo plazo, pídelo en `preguntas`."
)


def roadmap_pilares(roadmap: dict | None) -> list[str]:
    """Nombres EXACTOS de los pilares del roadmap. [] si no hay roadmap."""
    return [
        str(p["nombre"]).strip()
        for p in ((roadmap or {}).get("pilares") or [])
        if isinstance(p, dict) and str(p.get("nombre") or "").strip()
    ]


def _anio_key(roadmap: dict, period_year: int | None) -> str:
    """Qué año del roadmap (anio1|anio2|anio3) corresponde al periodo analizado.
    Misma convención que el PDF: el año calendario del 'Año 1' es anio_objetivo - 2."""
    try:
        base = int(roadmap.get("anio_objetivo")) - 2
        idx = int(period_year) - base + 1
    except (TypeError, ValueError):
        return "anio1"
    return _ANIOS[idx - 1] if 1 <= idx <= 3 else "anio1"


def _build_roadmap_context(roadmap: dict | None, period_year: int | None = None) -> str:
    """
    Resume el Roadmap Estratégico (documento rector) para el prompt del consejero.
    Si no hay roadmap, lo dice explícitamente: el agente no debe inventárselo.
    El estado ('borrador'/'validado') viaja en la clave `_status` del propio roadmap.
    """
    if not roadmap or not (
        roadmap.get("pilares") or roadmap.get("metas_3anios") or roadmap.get("vision")
    ):
        return SIN_ROADMAP

    estado = str(roadmap.get("_status") or "validado").strip().lower()
    if estado == "validado":
        cabecera = (
            "ROADMAP ESTRATÉGICO (VALIDADO POR EL DUEÑO — DOCUMENTO RECTOR):\n"
            "Es el plan oficial de la empresa. Tu trabajo es evaluar a la empresa CONTRA ESTE PLAN."
        )
    else:
        cabecera = (
            "ROADMAP ESTRATÉGICO (EN BORRADOR — el dueño todavía lo está revisando):\n"
            "Aún no está validado, así que trátalo como la intención declarada del dueño, no como "
            "compromiso firme. Aun así, evalúa a la empresa contra él y señala lo que no cuadre."
        )

    lines = [cabecera]
    if roadmap.get("vision"):
        lines.append(f"VISIÓN: {roadmap['vision']}")
    if roadmap.get("mision"):
        lines.append(f"MISIÓN: {roadmap['mision']}")

    metas = [m for m in (roadmap.get("metas_3anios") or []) if isinstance(m, dict) and m.get("meta")]
    if metas:
        lines.append("\nMETAS A 3 AÑOS:")
        for m in metas:
            kpi = f" [KPI: {m['kpi']}]" if m.get("kpi") else ""
            actual = m.get("valor_actual") or "no reportado"
            target = str(m.get("target") or "").strip()
            target_txt = target if target else "SIN FIJAR (el dueño aún no ha puesto el número; no lo inventes)"
            lines.append(f"  - {m['meta']}{kpi} — hoy: {actual} → meta: {target_txt}")

    pilares = [p for p in (roadmap.get("pilares") or []) if isinstance(p, dict) and p.get("nombre")]
    if pilares:
        key = _anio_key(roadmap, period_year)
        etiqueta = {"anio1": "Año 1", "anio2": "Año 2", "anio3": "Año 3"}[key]
        lines.append(f"\nPILARES ESTRATÉGICOS (con sus milestones del {etiqueta}, el año en curso):")
        for p in pilares:
            obj = str(p.get("objetivo") or p.get("descripcion") or "").strip()
            lines.append(f"  • {p['nombre']}" + (f" — {obj}" if obj else ""))
            miles = (p.get("milestones") or {}).get(key) if isinstance(p.get("milestones"), dict) else None
            for ms in (miles or []):
                lines.append(f"      - {ms}")
            if not miles:
                lines.append("      - (sin milestones definidos para este año)")

    return "\n".join(lines)


def _build_history_context(previous_analyses: list[dict]) -> str:
    if not previous_analyses:
        return ""
    lines = ["\nHISTORIAL DE SESIONES ANTERIORES (últimas 3):"]
    for entry in previous_analyses[-3:]:
        lines.append(
            f"  {entry.get('period', '')}: "
            f"{entry.get('summary', '')[:200]}"
        )
    return "\n".join(lines)


AGENT_SYSTEM_PROMPTS = {
    "CFO": """Eres el CFO Agent de Gobernia, consejero financiero de la empresa.
Tu rol: analizar la salud financiera, detectar riesgos de liquidez, evaluar márgenes y deuda.
Dimensiones bajo tu cargo: Finanzas.""",

    "CSO": """Eres el CSO Agent de Gobernia, consejero de estrategia comercial y capital humano.
Tu rol: evaluar crecimiento de ventas, concentración de clientes, rotación de personal y gaps de talento.
Dimensiones bajo tu cargo: Comercial, Recursos Humanos.""",

    "CRO": """Eres el CRO Agent de Gobernia, consejero de riesgos corporativos.
Tu rol: identificar y priorizar riesgos financieros, operativos, comerciales y de gobierno.
Dimensiones bajo tu cargo: Riesgos transversales.""",

    "Auditor": """Eres el Auditor Agent de Gobernia, consejero de gobierno y cumplimiento.
Tu rol: evaluar el Governance Score, acuerdos cumplidos, sesiones de consejo y brechas de cumplimiento.
Dimensiones bajo tu cargo: Gobierno, Cumplimiento.""",
}

# Qué documentos del board pack lee cada consejero (por document_type).
# `other` ("Otro documento") es material de apoyo general: lo leen TODOS — si no,
# el dueño lo sube, se le cobra el storage y ningún agente lo abre jamás.
AGENT_DOC_TYPES = {
    "CFO":     {"financial", "business_plan", "other"},
    "Auditor": {"audit_plan", "financial", "internal_rules", "bylaws", "other"},
    "CSO":     {"presentation", "business_plan", "other"},
    "CRO":     {"financial", "audit_plan", "presentation", "other"},
}

# Tokens del análisis del consejero. El esquema pide summary + findings + alerts +
# recommendations + preguntas: con 2048 el tool_use se truncaba a media respuesta.
ANALYSIS_MAX_TOKENS = 4096

# Regla antialucinación: se inyecta en el system prompt de análisis y de revisión.
ANTI_HALLUCINATION_RULE = """REGLA DE CITACIÓN (INQUEBRANTABLE):
- Si afirmas un dato tomado de un documento, DEBES citar la fuente en el campo `fuente`, con el
  nombre del documento y la página o sección exacta (ejemplo: "Estado de resultados, p. 4").
- Si no tienes un documento que respalde una afirmación, deja `fuente` vacía ("") y NO la presentes
  como dato duro: enúnciala como lectura, hipótesis o pregunta a validar con el dueño.
- NUNCA inventes cifras, citas, páginas ni contenido de documentos. Si un documento no se te adjuntó,
  no existe para ti: no supongas qué dice ni te refieras a él como si lo hubieras leído.
- Si no se te adjuntó ningún documento, todas las `fuente` van vacías y tu análisis se apoya solo en
  el contexto y los KPIs entregados.
- Si echas en falta un documento para sostener tu juicio, pídelo explícitamente en `preguntas`."""

# El Roadmap es el documento rector: los consejeros no analizan la empresa en abstracto,
# la analizan CONTRA el plan que el dueño se dio a sí mismo.
ROADMAP_RULE = """EL ROADMAP ES EL DOCUMENTO RECTOR:
- Analizas DOS insumos: el Roadmap Estratégico (el plan a 3 años del dueño) y los documentos de la
  sesión. El Roadmap manda: tu trabajo NO es opinar de la empresa en abstracto, es evaluarla CONTRA
  ESE PLAN — qué avanza, qué se atrasó, qué lo pone en riesgo, qué actividad no le sirve a ningún pilar.
- Ata tus hallazgos y recomendaciones a los pilares y metas del Roadmap siempre que puedas.
- Si el Roadmap no existe o no se te entregó, dilo y NO lo inventes: ni pilares, ni metas, ni milestones.
- Los `target` vacíos de las metas son vacíos de verdad (el dueño no los ha fijado): no supongas cifras."""

ANALYSIS_TOOL = {
    "name": "analisis_consejero",
    "description": "Entrega el análisis estructurado del consejero para el periodo.",
    "input_schema": {
        "type": "object",
        "properties": {
            "summary": {
                "type": "string",
                "description": "Resumen ejecutivo de 2-3 oraciones, dirigido al dueño.",
            },
            "findings": {
                "type": "array",
                "description": "Hallazgos del periodo, 2-5.",
                "items": {
                    "type": "object",
                    "properties": {
                        "texto": {"type": "string", "description": "El hallazgo, en una o dos oraciones."},
                        "fuente": {
                            "type": "string",
                            "description": (
                                "Documento y página de donde sale el dato "
                                "(ej. 'Estado de resultados, p. 4'). Vacío si no viene de un documento."
                            ),
                        },
                    },
                    "required": ["texto", "fuente"],
                },
            },
            "alerts": {
                "type": "array",
                "description": "Alertas con semáforo. Lista vacía si no hay nada que alertar.",
                "items": {
                    "type": "object",
                    "properties": {
                        "nivel": {
                            "type": "string",
                            "enum": ["rojo", "ambar", "verde"],
                            "description": "rojo = riesgo crítico; ambar = atención; verde = bajo control.",
                        },
                        "texto": {"type": "string"},
                        "fuente": {
                            "type": "string",
                            "description": "Documento y página que respalda la alerta; vacío si no aplica.",
                        },
                    },
                    "required": ["nivel", "texto", "fuente"],
                },
            },
            "recommendations": {
                "type": "array",
                "description": "Recomendaciones concretas: QUIÉN, CUÁNDO y CÓMO se mide el éxito.",
                "items": {"type": "string"},
            },
            "preguntas": {
                "type": "array",
                "description": (
                    "2-4 preguntas detonadoras para la junta, desde tu rol. "
                    "Preguntas que obliguen a decidir, no de relleno."
                ),
                "items": {"type": "string"},
            },
        },
        "required": ["summary", "findings", "alerts", "recommendations", "preguntas"],
    },
}


# ── Challenger Agent (pre-mortem / red team) ─────────────────────────────────

CHALLENGER_SYSTEM_PROMPT = """Eres el Challenger Agent de Gobernia: el consejero senior independiente
con 30 años de experiencia que cuestiona TODO. Tu trabajo NO es complacer ni validar.
Tu trabajo es proteger al empresario de análisis blandos, optimistas o genéricos.

Tu método es el PRE-MORTEM: imagina que han pasado 12 meses y el plan recomendado por
este agente FRACASÓ ROTUNDAMENTE. Tu tarea es identificar exactamente por qué.

Cuestiona específicamente:
1. SUPUESTOS DÉBILES: ¿qué asume el análisis sin evidencia que lo respalde?
2. RIESGOS OMITIDOS: ¿qué riesgo crítico no mencionó? (consulta los 10 riesgos
   estratégicos del CCE y los 10 temas prioritarios 2026)
3. RECOMENDACIONES VAGAS: si una recomendación no dice QUIÉN, CUÁNDO, ni CÓMO MEDIR
   éxito, es humo. Señálalo.
4. DATOS IGNORADOS: ¿los KPIs/datos de la empresa contradicen alguna conclusión?
5. PUNTOS CIEGOS: ¿el análisis solo contempla escenarios positivos? ¿ignora el peor caso?
6. ALINEACIÓN A FRAMEWORKS: ¿faltó referenciar alguna mejor práctica del CCE aplicable?
7. SESGO DE COMPLACENCIA: ¿el agente está siendo amable o evitando una conversación difícil?

NO escribas un análisis nuevo. NO repitas lo que el agente ya dijo. Escribe SOLO
críticas accionables, breves, directas. Si encuentras pocas o ninguna debilidad
real, sé honesto y dilo — no inventes problemas para parecer riguroso."""

_CRITIQUE_LIST_FIELDS = (
    "weak_assumptions", "missing_risks", "vague_recommendations",
    "ignored_data", "blind_spots", "framework_gaps",
)

CHALLENGER_TOOL = {
    "name": "critica_challenger",
    "description": "Entrega la crítica pre-mortem del análisis del consejero.",
    "input_schema": {
        "type": "object",
        "properties": {
            **{
                f: {"type": "array", "items": {"type": "string"}}
                for f in _CRITIQUE_LIST_FIELDS
            },
            "verdict": {
                "type": "string",
                "description": "Una oración: ¿qué tan robusto es el análisis original?",
            },
        },
        "required": [*_CRITIQUE_LIST_FIELDS, "verdict"],
    },
}


def _tool_input(response, tool_name: str) -> dict | None:
    """Lee el bloque tool_use de la respuesta de Claude. None si no lo devolvió."""
    for block in getattr(response, "content", None) or []:
        if getattr(block, "type", None) == "tool_use" and getattr(block, "name", None) == tool_name:
            data = getattr(block, "input", None)
            if isinstance(data, dict):
                return dict(data)
    return None


def _usable_analysis(response, tool_name: str) -> dict | None:
    """
    El análisis del tool_use, o None si no sirve.
    Si el modelo se queda sin tokens, Anthropic devuelve el tool_use con el input a
    medias (a veces `{}`): un dict vacío o sin `summary` es un fallo, no un análisis
    — si no, la UI pinta una tarjeta de consejero en blanco y nadie se entera.
    """
    if getattr(response, "stop_reason", None) == "max_tokens":
        _log.warning("respuesta truncada por max_tokens; se descarta el tool_use parcial")
        return None
    data = _tool_input(response, tool_name)
    if not data or not str(data.get("summary") or "").strip():
        return None
    return data


def _fuentes_de(analysis: dict) -> set[str]:
    """Todas las `fuente` citadas (no vacías) en findings y alerts."""
    a = normalize_analysis(analysis)
    return {
        item["fuente"].strip()
        for item in (*a["findings"], *a["alerts"])
        if item.get("fuente", "").strip()
    }


def _filtrar_fuentes(analysis: dict, permitidas: set[str] | None) -> dict:
    """
    Deja en blanco toda `fuente` que no esté en `permitidas`.
    `permitidas=None` (o vacío) → se vacían todas.
    Es la verificación determinista de la regla antialucinación: el prompt la pide,
    pero solo el backend puede garantizarla.
    """
    ok = permitidas or set()
    out = dict(analysis)
    for campo in ("findings", "alerts"):
        out[campo] = [
            {**item, "fuente": item["fuente"] if item.get("fuente", "").strip() in ok else ""}
            for item in (out.get(campo) or [])
        ]
    return out


def run_challenger_critique(
    agent: str,
    initial_analysis: dict,
    memory_buffer: dict,
    kpi_snapshot: dict | None,
    period_year: int,
    period_month: int,
) -> dict:
    """
    Critica adversarial del análisis inicial de un agente.
    Aplica pre-mortem para encontrar debilidades antes de mostrar al usuario.
    """
    if not settings.ANTHROPIC_API_KEY:
        return {}

    company_ctx = _build_company_context(memory_buffer)
    kpi_ctx = _build_kpi_context(kpi_snapshot, memory_buffer)
    is_family = bool(memory_buffer.get("company", {}).get("is_family_business"))
    knowledge_ctx = build_knowledge_for_agent(agent, is_family_business=is_family)

    user_prompt = (
        f"Estás revisando el análisis del agente {agent} para el periodo "
        f"{_period_label(period_year, period_month)}.\n\n"
        f"CONTEXTO DE LA EMPRESA:\n{company_ctx}\n\n"
        f"{kpi_ctx}\n\n"
        f"FRAMEWORKS APLICABLES (úsalos para detectar brechas):\n{knowledge_ctx}\n\n"
        f"ANÁLISIS DEL AGENTE {agent} A CUESTIONAR:\n"
        f"{json.dumps(initial_analysis, ensure_ascii=False, indent=2)}\n\n"
        "Aplica el método pre-mortem: si en 12 meses este plan fracasa, ¿por qué fue? "
        "Entrega la crítica con la herramienta 'critica_challenger'. "
        "Si un campo no tiene críticas reales, devuélvelo como lista vacía []."
    )

    client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    response = _create_with_retry(client,
        model=settings.AI_MODEL,
        max_tokens=2048,
        system=CHALLENGER_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_prompt}],
        tools=[CHALLENGER_TOOL],
        tool_choice={"type": "tool", "name": CHALLENGER_TOOL["name"]},
    )
    critique = _tool_input(response, CHALLENGER_TOOL["name"])
    return critique if critique is not None else {}


def run_agent_revision(
    agent: str,
    initial_analysis: dict,
    critique: dict,
    memory_buffer: dict,
    kpi_snapshot: dict | None,
    period_year: int,
    period_month: int,
    previous_analyses: list[dict] | None = None,
) -> dict:
    """
    El agente revisa su análisis basado en la crítica del Challenger.
    Si la crítica está vacía o el agente no tiene API key, devuelve el original.
    """
    if not settings.ANTHROPIC_API_KEY:
        return initial_analysis

    has_critique = any(critique.get(k) for k in _CRITIQUE_LIST_FIELDS)
    if not has_critique:
        return initial_analysis

    agent_cfg = _get_agent_config(memory_buffer, agent)
    tone = agent_cfg.get("tone", "formal")
    sensitivity = agent_cfg.get("alert_sensitivity", "medium")
    custom = agent_cfg.get("custom_instructions") or ""

    company_ctx = _build_company_context(memory_buffer)
    kpi_ctx = _build_kpi_context(kpi_snapshot, memory_buffer)
    history_ctx = _build_history_context(previous_analyses or [])
    is_family = bool(memory_buffer.get("company", {}).get("is_family_business"))
    knowledge_ctx = build_knowledge_for_agent(agent, is_family_business=is_family)

    system_prompt = (
        f"{AGENT_SYSTEM_PROMPTS[agent]}\n\n"
        f"TONO: {tone}. SENSIBILIDAD DE ALERTAS: {sensitivity}.\n"
        + (f"INSTRUCCIONES ADICIONALES: {custom}\n" if custom else "")
        + f"\n{ANTI_HALLUCINATION_RULE}\n"
        + f"\n{knowledge_ctx}\n"
    )

    user_prompt = (
        f"Periodo: {_period_label(period_year, period_month)}.\n\n"
        f"{company_ctx}\n\n{kpi_ctx}\n{history_ctx}\n\n"
        f"TU ANÁLISIS INICIAL FUE:\n"
        f"{json.dumps(initial_analysis, ensure_ascii=False, indent=2)}\n\n"
        f"UN CONSEJERO SENIOR INDEPENDIENTE LO REVISÓ Y LE HIZO ESTAS OBSERVACIONES:\n"
        f"{json.dumps(critique, ensure_ascii=False, indent=2)}\n\n"
        "Revisa tu análisis incorporando esas críticas:\n"
        "1. Atiende cada observación de manera directa, no la rodees.\n"
        "2. Si una recomendación era vaga, hazla específica: agrega QUIÉN ejecuta, "
        "CUÁNDO se hace, y CÓMO se medirá el éxito.\n"
        "3. Reconoce los riesgos omitidos en findings o alerts.\n"
        "4. Si la crítica no aplica o es incorrecta, mantén tu posición — no cedas por ceder.\n"
        "5. Mantén el tono y el estilo del análisis original; solo fortalécelo.\n"
        "6. NO tienes los documentos a la vista en esta revisión: conserva tal cual las `fuente` "
        "que ya habías citado y NO inventes fuentes nuevas.\n\n"
        "Entrega el análisis revisado con la herramienta 'analisis_consejero'."
    )

    client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    response = _create_with_retry(client,
        model=settings.AI_MODEL,
        max_tokens=ANALYSIS_MAX_TOKENS,
        system=system_prompt,
        messages=[{"role": "user", "content": user_prompt}],
        tools=[ANALYSIS_TOOL],
        tool_choice={"type": "tool", "name": ANALYSIS_TOOL["name"]},
    )
    revised = _usable_analysis(response, ANALYSIS_TOOL["name"])
    # Si el modelo no devolvió una revisión utilizable, conservamos el análisis original.
    if revised is None:
        return initial_analysis
    # La revisión NO tiene los documentos a la vista: solo puede sostener las fuentes que
    # ya citó el análisis inicial. Cualquier fuente nueva es inventada → se vacía.
    return _filtrar_fuentes(normalize_analysis(revised), _fuentes_de(initial_analysis))


def _parse_json_loose(raw: str) -> dict:
    """Parseo permisivo de JSON. Si falla, retorna dict vacío."""
    parsed = _extract_json_object(raw)
    return parsed if parsed is not None else {}


def _extract_json_object(raw: str) -> dict | None:
    """
    Extrae el primer objeto JSON válido de un texto. Maneja:
    - JSON envuelto en markdown ```json ... ```
    - Texto explicativo antes/después del JSON
    - JSON truncado al final (intenta cerrar llaves faltantes)
    """
    import re
    if not raw:
        return None

    # Quitar wrapper de markdown si existe
    md = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, re.DOTALL)
    candidate = md.group(1) if md else None

    # Si no había markdown, buscar el primer { y emparejar llaves
    if candidate is None:
        start = raw.find("{")
        if start == -1:
            return None
        depth = 0
        in_str = False
        escape = False
        end = -1
        for i in range(start, len(raw)):
            ch = raw[i]
            if escape:
                escape = False
                continue
            if ch == "\\":
                escape = True
                continue
            if ch == '"':
                in_str = not in_str
                continue
            if in_str:
                continue
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    end = i + 1
                    break
        candidate = raw[start:end] if end > 0 else raw[start:] + "}" * max(depth, 0)

    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        # Último intento: cerrar llaves faltantes si la respuesta quedó truncada
        try:
            missing = candidate.count("{") - candidate.count("}")
            if missing > 0:
                return json.loads(candidate + "}" * missing)
        except json.JSONDecodeError:
            pass
    return None


def run_agent_analysis(
    agent: str,
    memory_buffer: dict,
    kpi_snapshot: dict | None,
    period_year: int,
    period_month: int,
    previous_analyses: list[dict] | None = None,
    documents: list[dict] | None = None,
    documents_note: str = "",
    roadmap: dict | None = None,
) -> dict:
    """
    Llama a Claude con el contexto completo y retorna el análisis estructurado.
    `documents`: board pack del agente — [{kind, media_type, data (base64), label}].
    `documents_note`: aviso sobre documentos que no se pudieron adjuntar (xlsx/docx...).
    `roadmap`: Roadmap Estratégico del dueño (documento rector). None → el prompt lo dice.
    Si ANTHROPIC_API_KEY no está configurada, retorna análisis placeholder.
    """
    agent_cfg = _get_agent_config(memory_buffer, agent)
    tone = agent_cfg.get("tone", "formal")
    sensitivity = agent_cfg.get("alert_sensitivity", "medium")
    custom = agent_cfg.get("custom_instructions") or ""

    if not settings.ANTHROPIC_API_KEY:
        return _placeholder_analysis(agent, period_year, period_month)

    company_ctx = _build_company_context(memory_buffer)
    kpi_ctx = _build_kpi_context(kpi_snapshot, memory_buffer)
    history_ctx = _build_history_context(previous_analyses or [])
    roadmap_ctx = _build_roadmap_context(roadmap, period_year)
    is_family = bool(memory_buffer.get("company", {}).get("is_family_business"))
    knowledge_ctx = build_knowledge_for_agent(agent, is_family_business=is_family)

    system_prompt = (
        f"{AGENT_SYSTEM_PROMPTS[agent]}\n\n"
        f"TONO: {tone}. SENSIBILIDAD DE ALERTAS: {sensitivity}.\n"
        + (f"INSTRUCCIONES ADICIONALES: {custom}\n" if custom else "")
        + f"\n{ROADMAP_RULE}\n"
        + f"\n{ANTI_HALLUCINATION_RULE}\n"
        + f"\n{knowledge_ctx}\n"
    )

    if documents:
        docs_intro = (
            "\nDOCUMENTOS DE LA SESIÓN (los de tu competencia): se adjuntan antes de estas "
            "instrucciones, cada uno precedido por su descripción. Léelos y apóyate en ellos; "
            "cita documento y página en `fuente` cada vez que uses un dato de ellos.\n"
        )
    else:
        docs_intro = (
            "\nNo se adjuntó ningún documento de tu competencia a esta sesión: trabaja solo con el "
            "contexto y los KPIs, deja todas las `fuente` vacías y, si necesitas un documento para "
            "sostener tu juicio, pídelo en `preguntas`.\n"
        )
    nota_docs = f"NOTA SOBRE DOCUMENTOS: {documents_note}\n" if documents_note else ""

    user_prompt = (
        f"Estás analizando el periodo: {_period_label(period_year, period_month)}.\n\n"
        f"{company_ctx}\n\n"
        f"{roadmap_ctx}\n\n"
        f"{kpi_ctx}\n"
        f"{history_ctx}\n"
        f"{docs_intro}"
        f"{nota_docs}\n"
        "Genera tu análisis como consejero, evaluando a la empresa contra su Roadmap y contra los "
        "documentos de la sesión, y entrégalo con la herramienta 'analisis_consejero'."
    )

    content = build_doc_blocks(documents) + [{"type": "text", "text": user_prompt}] \
        if documents else user_prompt

    client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    response = _create_with_retry(client,
        model=settings.AI_MODEL,
        max_tokens=ANALYSIS_MAX_TOKENS,
        system=system_prompt,
        messages=[{"role": "user", "content": content}],
        tools=[ANALYSIS_TOOL],
        tool_choice={"type": "tool", "name": ANALYSIS_TOOL["name"]},
    )

    parsed = _usable_analysis(response, ANALYSIS_TOOL["name"])
    if parsed is None:
        return _placeholder_analysis(agent, period_year, period_month)

    analysis = normalize_analysis(parsed)
    if not documents:
        # No se le adjuntó ningún documento: no hay fuente posible que citar.
        analysis = _filtrar_fuentes(analysis, permitidas=None)
    return analysis


def run_agent_chat(
    agent: str,
    user_message: str,
    memory_buffer: dict,
    kpi_snapshot: dict | None,
    chat_history: list[dict],
    period_year: int,
    period_month: int,
) -> str:
    """
    Responde a un mensaje del usuario en el chat de la sesión de consejo.
    """
    agent_cfg = _get_agent_config(memory_buffer, agent)
    tone = agent_cfg.get("tone", "formal")
    custom = agent_cfg.get("custom_instructions") or ""

    if not settings.ANTHROPIC_API_KEY:
        return f"[{agent} Agent] Análisis disponible cuando se configure ANTHROPIC_API_KEY."

    company_ctx = _build_company_context(memory_buffer)
    kpi_ctx = _build_kpi_context(kpi_snapshot, memory_buffer)
    is_family = bool(memory_buffer.get("company", {}).get("is_family_business"))
    knowledge_ctx = build_knowledge_for_agent(agent, is_family_business=is_family)

    system_prompt = (
        f"{AGENT_SYSTEM_PROMPTS[agent]}\n\n"
        f"TONO: {tone}. Periodo actual: {_period_label(period_year, period_month)}.\n"
        f"{company_ctx}\n\n{kpi_ctx}\n"
        + (f"INSTRUCCIONES ADICIONALES: {custom}\n" if custom else "")
        + f"\n{knowledge_ctx}\n"
        + "\nResponde de forma concisa y accionable. No uses JSON, responde en prosa."
    )

    # Construir historial de mensajes para Claude
    messages = []
    for msg in chat_history[-10:]:  # últimos 10 mensajes para contexto
        role = "user" if msg["role"] == "user" else "assistant"
        messages.append({"role": role, "content": msg["content"]})
    messages.append({"role": "user", "content": user_message})

    client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    response = _create_with_retry(client,
        model=settings.AI_MODEL,
        max_tokens=800,
        system=system_prompt,
        messages=messages,
    )
    return response.content[0].text


async def run_agent_chat_stream(
    agent: str,
    user_message: str,
    memory_buffer: dict,
    kpi_snapshot: dict | None,
    chat_history: list[dict],
    period_year: int,
    period_month: int,
) -> AsyncIterator[str]:
    """
    Versión streaming de run_agent_chat. Yields cada fragmento de texto
    a medida que Claude lo va generando, para mostrar la respuesta
    apareciendo en tiempo real al usuario.
    """
    if not settings.ANTHROPIC_API_KEY:
        yield f"[{agent} Agent] Análisis disponible cuando se configure ANTHROPIC_API_KEY."
        return

    agent_cfg = _get_agent_config(memory_buffer, agent)
    tone = agent_cfg.get("tone", "formal")
    custom = agent_cfg.get("custom_instructions") or ""

    company_ctx = _build_company_context(memory_buffer)
    kpi_ctx = _build_kpi_context(kpi_snapshot, memory_buffer)
    is_family = bool(memory_buffer.get("company", {}).get("is_family_business"))
    knowledge_ctx = build_knowledge_for_agent(agent, is_family_business=is_family)

    system_prompt = (
        f"{AGENT_SYSTEM_PROMPTS[agent]}\n\n"
        f"TONO: {tone}. Periodo actual: {_period_label(period_year, period_month)}.\n"
        f"{company_ctx}\n\n{kpi_ctx}\n"
        + (f"INSTRUCCIONES ADICIONALES: {custom}\n" if custom else "")
        + f"\n{knowledge_ctx}\n"
        + "\nResponde de forma concisa y accionable. No uses JSON, responde en prosa."
    )

    messages = []
    for msg in chat_history[-10:]:
        role = "user" if msg["role"] == "user" else "assistant"
        messages.append({"role": role, "content": msg["content"]})
    messages.append({"role": "user", "content": user_message})

    client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
    async with client.messages.stream(
        model=settings.AI_MODEL,
        max_tokens=800,
        system=system_prompt,
        messages=messages,
    ) as stream:
        async for text in stream.text_stream:
            yield text


def _placeholder_analysis(agent: str, year: int, month: int) -> dict:
    """Placeholder cuando la API key no está configurada O cuando el parseo falla."""
    if not settings.ANTHROPIC_API_KEY:
        return {
            "summary": (
                f"{agent} Agent listo para {_period_label(year, month)}. "
                "Configura ANTHROPIC_API_KEY para activar el análisis con IA."
            ),
            "findings": [{"texto": "Datos recibidos correctamente.", "fuente": ""}],
            "alerts": [],
            "recommendations": ["Ingresa los KPIs del periodo para recibir análisis."],
            "preguntas": [],
        }
    # API key sí está, pero el modelo no devolvió la herramienta
    return {
        "summary": (
            f"El {agent} Agent recibió tu información para {_period_label(year, month)} pero "
            "no logró formatear la respuesta. Vuelve a generar el análisis."
        ),
        "findings": [],
        "alerts": [],
        "recommendations": ["Da click en 'Generar análisis' nuevamente."],
        "preguntas": [],
    }


def failed_agent_analysis(agent: str, year: int, month: int) -> dict:
    """
    Placeholder cuando el pipeline de UN agente revienta (documento ilegible, PDF cifrado,
    error de la API...). Los demás consejeros siguen y lo que sí se logró se persiste.
    """
    return {
        "summary": (
            f"No pude completar el análisis del {agent} para {_period_label(year, month)}. "
            "Revisa que los documentos sean PDF válidos, no estén protegidos con contraseña "
            "y vuelve a generar el análisis."
        ),
        "findings": [],
        "alerts": [],
        "recommendations": [
            "Revisa los documentos de esta sesión y vuelve a generar el análisis.",
        ],
        "preguntas": [],
        "_error": True,
    }


def _parse_json(raw: str, agent: str, year: int, month: int) -> dict:
    parsed = _extract_json_object(raw)
    if parsed is not None:
        return parsed
    return _placeholder_analysis(agent, year, month)
