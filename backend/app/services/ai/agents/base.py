"""
Base del agente IA — construye el prompt del sistema y llama a Claude.
Cada agente (CFO, CSO, CRO, Auditor) hereda de aquí.
"""
import json
import anthropic

from app.core.config import settings

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

    system_prompt = (
        f"{AGENT_SYSTEM_PROMPTS[agent]}\n\n"
        f"TONO: {tone}. SENSIBILIDAD DE ALERTAS: {sensitivity}.\n"
        + (f"INSTRUCCIONES ADICIONALES: {custom}\n" if custom else "")
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
        max_tokens=1024,
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

    system_prompt = (
        f"{AGENT_SYSTEM_PROMPTS[agent]}\n\n"
        f"TONO: {tone}. Periodo actual: {_period_label(period_year, period_month)}.\n"
        f"{company_ctx}\n\n{kpi_ctx}\n"
        + (f"INSTRUCCIONES ADICIONALES: {custom}\n" if custom else "")
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


def _placeholder_analysis(agent: str, year: int, month: int) -> dict:
    return {
        "summary": (
            f"{agent} Agent listo para {_period_label(year, month)}. "
            "Configura ANTHROPIC_API_KEY para activar el análisis con IA."
        ),
        "findings": ["Datos recibidos correctamente."],
        "alerts": [],
        "recommendations": ["Ingresa los KPIs del periodo para recibir análisis."],
    }


def _parse_json(raw: str, agent: str, year: int, month: int) -> dict:
    import re
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass
    return _placeholder_analysis(agent, year, month)
