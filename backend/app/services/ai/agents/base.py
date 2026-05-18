"""
Base del agente IA — construye el prompt del sistema y llama a Claude.
Cada agente (CFO, CSO, CRO, Auditor) hereda de aquí.
"""
import json
from typing import AsyncIterator

import anthropic

from app.core.config import settings
from app.services.ai.knowledge_base import build_knowledge_for_agent

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

ANALYSIS_SCHEMA = """{
  "summary": "Resumen ejecutivo de 2-3 oraciones",
  "findings": ["hallazgo 1", "hallazgo 2", "hallazgo 3"],
  "alerts": ["alerta crítica si existe"],
  "recommendations": ["recomendación concreta 1", "recomendación concreta 2"]
}"""


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

CHALLENGER_CRITIQUE_SCHEMA = """{
  "weak_assumptions": ["supuesto débil 1", "..."],
  "missing_risks": ["riesgo no mencionado 1", "..."],
  "vague_recommendations": ["recomendación 1 es vaga porque no dice X, falta Y", "..."],
  "ignored_data": ["el dato Z contradice esto", "..."],
  "blind_spots": ["punto ciego 1", "..."],
  "framework_gaps": ["mejor práctica CCE no aplicada", "..."],
  "verdict": "una oración: ¿qué tan robusto es el análisis original?"
}"""


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
        "Responde ÚNICAMENTE con JSON válido siguiendo este esquema. "
        "Si un campo no tiene críticas reales, devuélvelo como lista vacía []:\n"
        f"{CHALLENGER_CRITIQUE_SCHEMA}"
    )

    client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    response = client.messages.create(
        model=settings.AI_MODEL,
        max_tokens=2048,
        system=CHALLENGER_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_prompt}],
    )
    raw = response.content[0].text
    return _parse_json_loose(raw)


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

    has_critique = any(
        critique.get(k) for k in (
            "weak_assumptions", "missing_risks", "vague_recommendations",
            "ignored_data", "blind_spots", "framework_gaps",
        )
    )
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
        "5. Mantén el tono y el estilo del análisis original; solo fortalécelo.\n\n"
        "Responde ÚNICAMENTE con JSON válido en el mismo esquema original:\n"
        f"{ANALYSIS_SCHEMA}"
    )

    client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    response = client.messages.create(
        model=settings.AI_MODEL,
        max_tokens=2048,
        system=system_prompt,
        messages=[{"role": "user", "content": user_prompt}],
    )
    raw = response.content[0].text
    # Si la revisión falla parseo, devolver el análisis original en lugar de placeholder
    parsed_raw = _extract_json_object(raw)
    return parsed_raw if parsed_raw is not None else initial_analysis


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
) -> dict:
    """
    Llama a Claude con el contexto completo y retorna el análisis estructurado.
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
    is_family = bool(memory_buffer.get("company", {}).get("is_family_business"))
    knowledge_ctx = build_knowledge_for_agent(agent, is_family_business=is_family)

    system_prompt = (
        f"{AGENT_SYSTEM_PROMPTS[agent]}\n\n"
        f"TONO: {tone}. SENSIBILIDAD DE ALERTAS: {sensitivity}.\n"
        + (f"INSTRUCCIONES ADICIONALES: {custom}\n" if custom else "")
        + f"\n{knowledge_ctx}\n"
    )

    user_prompt = (
        f"Estás analizando el periodo: {_period_label(period_year, period_month)}.\n\n"
        f"{company_ctx}\n\n"
        f"{kpi_ctx}\n"
        f"{history_ctx}\n\n"
        "Genera tu análisis como consejero. Responde ÚNICAMENTE con JSON válido:\n"
        f"{ANALYSIS_SCHEMA}"
    )

    client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    response = client.messages.create(
        model=settings.AI_MODEL,
        max_tokens=2048,
        system=system_prompt,
        messages=[{"role": "user", "content": user_prompt}],
    )

    raw = response.content[0].text
    return _parse_json(raw, agent, period_year, period_month)


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
    response = client.messages.create(
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
            "findings": ["Datos recibidos correctamente."],
            "alerts": [],
            "recommendations": ["Ingresa los KPIs del periodo para recibir análisis."],
        }
    # API key sí está, pero el modelo devolvió algo no parseable
    return {
        "summary": (
            f"El {agent} Agent recibió tu información para {_period_label(year, month)} pero "
            "no logró formatear la respuesta. Vuelve a generar el análisis."
        ),
        "findings": [],
        "alerts": [],
        "recommendations": ["Da click en 'Generar análisis' nuevamente."],
    }


def _parse_json(raw: str, agent: str, year: int, month: int) -> dict:
    parsed = _extract_json_object(raw)
    if parsed is not None:
        return parsed
    return _placeholder_analysis(agent, year, month)
