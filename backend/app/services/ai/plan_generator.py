"""
Generador de Plan de Acción.
Toma los 4 análisis ya revisados (post-Challenger) y los convierte en
un conjunto de tareas accionables con responsable, prioridad y plazo.
"""
import json

import anthropic

from app.core.config import settings
from app.services.ai.agents.base import _extract_json_object


PLAN_GENERATOR_SYSTEM_PROMPT = """Eres el director del consejo. Tu trabajo es traducir los análisis
de los 4 agentes (CFO, CSO, CRO, Auditor) en un PLAN DE ACCIÓN concreto y ejecutable.

Reglas para cada tarea que generes:
1. TÍTULO: una línea corta y accionable. Empieza con un verbo en infinitivo
   (Documentar, Implementar, Revisar, Definir, etc.). Máximo 80 caracteres.
2. DESCRIPCIÓN: 1-2 oraciones que expliquen QUÉ se debe hacer y POR QUÉ.
3. OWNER (rol responsable): elige el más natural — "Director General", "CFO",
   "Director Comercial", "Director de RH", "Consejo de Administración", "Auditor Interno",
   "Secretario del Consejo", "Comité de Riesgos", etc.
4. PRIORIDAD:
   - "alta" → si el agente lo marcó como alerta o riesgo estratégico
   - "media" → recomendación importante pero no crítica
   - "baja" → mejora incremental
5. SOURCE_AGENT: el agente del que sale la tarea (CFO, CSO, CRO o Auditor).
6. DUE_HORIZON: "30d" (ejecución inmediata), "90d" (un trimestre), "180d" (medio año).
7. TAGS: máximo 2 etiquetas cortas en minúsculas (ej. "compliance", "liquidez",
   "talento", "ciberseguridad", "sucesión").

NO inventes tareas que no estén respaldadas por los análisis. NO repitas tareas con
distinto título. Si dos agentes recomiendan lo mismo, fusiona en UNA tarea con prioridad
más alta. Devuelve entre 6 y 15 tareas — calidad sobre cantidad."""

PLAN_OUTPUT_SCHEMA = """{
  "tasks": [
    {
      "title": "string",
      "description": "string",
      "source_agent": "CFO|CSO|CRO|Auditor",
      "priority": "alta|media|baja",
      "owner": "string",
      "due_horizon": "30d|90d|180d",
      "tags": ["tag1", "tag2"]
    }
  ]
}"""


def _due_date_from_horizon(horizon: str) -> str | None:
    """Convierte '30d' / '90d' / '180d' a una fecha ISO desde hoy."""
    from datetime import date, timedelta
    days = {"30d": 30, "90d": 90, "180d": 180}.get(horizon)
    if days is None:
        return None
    return (date.today() + timedelta(days=days)).isoformat()


def generate_action_plan(
    agent_analyses: dict[str, dict],
    memory_buffer: dict,
    period_label: str,
) -> list[dict]:
    """
    Llama a Claude para convertir los análisis en tareas accionables.
    Retorna lista de dicts con campos compatibles con ActionTaskCreate.
    Si no hay API key, fallback determinista que extrae recommendations.
    """
    if not settings.ANTHROPIC_API_KEY:
        return _fallback_plan_from_analyses(agent_analyses)

    company = memory_buffer.get("company", {})
    company_name = company.get("name", "la empresa")
    industry = company.get("industry", "")

    user_prompt = (
        f"Empresa: {company_name} | Industria: {industry} | Periodo analizado: {period_label}\n\n"
        f"ANÁLISIS DE LOS 4 AGENTES (ya revisados con pre-mortem):\n"
        f"{json.dumps(agent_analyses, ensure_ascii=False, indent=2)}\n\n"
        "Genera el plan de acción. Responde ÚNICAMENTE con JSON válido siguiendo este esquema:\n"
        f"{PLAN_OUTPUT_SCHEMA}"
    )

    client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    response = client.messages.create(
        model=settings.AI_MODEL,
        max_tokens=4096,
        system=PLAN_GENERATOR_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_prompt}],
    )
    raw = response.content[0].text
    parsed = _extract_json_object(raw)
    if not parsed or not isinstance(parsed.get("tasks"), list):
        return _fallback_plan_from_analyses(agent_analyses)

    tasks_out = []
    for idx, t in enumerate(parsed["tasks"]):
        if not isinstance(t, dict) or not t.get("title"):
            continue
        tasks_out.append({
            "title":        str(t.get("title", ""))[:200],
            "description":  str(t.get("description", "")) if t.get("description") else None,
            "source_agent": _normalize_agent(t.get("source_agent")),
            "priority":     _normalize_priority(t.get("priority")),
            "owner":        str(t.get("owner", "")) if t.get("owner") else None,
            "due_date":     _due_date_from_horizon(str(t.get("due_horizon", ""))),
            "tags":         _normalize_tags(t.get("tags")),
            "order_index":  idx,
        })
    return tasks_out


def _normalize_agent(v) -> str | None:
    if not isinstance(v, str):
        return None
    cleaned = v.strip().lower()
    mapping = {"cfo": "CFO", "cso": "CSO", "cro": "CRO", "auditor": "Auditor"}
    return mapping.get(cleaned)


def _normalize_priority(v) -> str:
    if isinstance(v, str) and v.lower() in {"alta", "media", "baja"}:
        return v.lower()
    return "media"


def _normalize_tags(v) -> list[str]:
    if not isinstance(v, list):
        return []
    return [str(t).lower().strip()[:30] for t in v if t][:3]


def _fallback_plan_from_analyses(agent_analyses: dict[str, dict]) -> list[dict]:
    """Plan determinista cuando no hay API key: una tarea por recomendación."""
    tasks = []
    idx = 0
    for agent, analysis in agent_analyses.items():
        if not isinstance(analysis, dict):
            continue
        alerts = analysis.get("alerts") or []
        recs = analysis.get("recommendations") or []
        for a in alerts:
            tasks.append({
                "title":        str(a)[:200],
                "description":  None,
                "source_agent": agent,
                "priority":     "alta",
                "owner":        None,
                "due_date":     _due_date_from_horizon("30d"),
                "tags":         [],
                "order_index":  idx,
            })
            idx += 1
        for r in recs:
            tasks.append({
                "title":        str(r)[:200],
                "description":  None,
                "source_agent": agent,
                "priority":     "media",
                "owner":        None,
                "due_date":     _due_date_from_horizon("90d"),
                "tags":         [],
                "order_index":  idx,
            })
            idx += 1
    return tasks
