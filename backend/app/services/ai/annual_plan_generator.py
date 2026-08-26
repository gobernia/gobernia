"""
Generador del Plan Estratégico de 12 meses.

Tres pasos (orquestados por app.tasks.annual_plan_tasks):
1. DIAGNÓSTICO  — reutiliza los 4 agentes + Challenger (board.base).
2. ESQUELETO    — 1 llamada → 12 meses con focus + objetivos + kpi_refs.
3. TAREAS       — por mes, tareas de cada objetivo (owner/prioridad/due/kpi_ref).

La lógica pura (calendario, parseo, mapeo, fallback) vive aquí y se testea sin DB ni red.
"""
import calendar
import json
from datetime import date

import anthropic

from app.core.config import settings
from app.services.ai.agents.base import _create_with_retry, _extract_json_object
from app.services.ai.prompt_loader import load_prompt


# ── Helpers de calendario ───────────────────────────────────────────────────

def month_calendar(start_year: int, start_month: int, month_index: int) -> tuple[int, int]:
    """Dado el mes de inicio y un month_index 1..12, retorna (año, mes) calendario."""
    zero_based = (start_year * 12 + (start_month - 1)) + (month_index - 1)
    return zero_based // 12, zero_based % 12 + 1


def compute_active_month_index(start_date: date, today: date, total_months: int = 12) -> int:
    """Índice (1..total_months) del mes vigente del plan según hoy. Cap en [1, total_months]."""
    elapsed = (today.year - start_date.year) * 12 + (today.month - start_date.month)
    return min(max(elapsed + 1, 1), total_months)


def due_date_within_month(year: int, month: int, day: int = 28) -> date:
    """Construye una fecha dentro del mes, clampeando el día a [1, último día del mes]."""
    last = calendar.monthrange(year, month)[1]
    return date(year, month, min(max(day, 1), last))


# ── Normalización ───────────────────────────────────────────────────────────

_PRIORITIES = {"alta", "media", "baja"}


_AGENDA_TYPES = {"informacion", "seguimiento", "deliberacion", "decision"}
_LEAD_AGENTS = {"CFO", "CSO", "CRO", "Auditor"}


def _norm_agenda_fields(t: dict) -> dict:
    """Campos de agenda de gobierno del punto (revisión del cliente): consejero
    líder, naturaleza del punto y decisión esperada. None si no vienen o no son válidos."""
    lead = str(t.get("lead_agent") or "").strip()
    atype = str(t.get("agenda_type") or "").strip().lower()
    decision = str(t.get("decision_expected") or "").strip()
    return {
        "lead_agent": lead if lead in _LEAD_AGENTS else None,
        "agenda_type": atype if atype in _AGENDA_TYPES else None,
        "decision_expected": decision[:400] or None,
    }


def _norm_priority(v) -> str:
    return v.lower() if isinstance(v, str) and v.lower() in _PRIORITIES else "media"


def _norm_tags(v) -> list[str]:
    if not isinstance(v, list):
        return []
    return [str(t).lower().strip()[:30] for t in v if t][:3]


def fallback_skeleton() -> list[dict]:
    """Esqueleto determinista de 12 meses sin objetivos (cuando no hay API key o falla)."""
    return [{"month_index": i, "focus": None, "objectives": []} for i in range(1, 13)]


def parse_skeleton(raw: str) -> list[dict]:
    """
    Parsea la respuesta del LLM a una lista de EXACTAMENTE 12 meses ordenados.
    Cada mes: {month_index, focus, objectives:[{title, description, kpi_refs}]}.
    Rellena meses faltantes con objetivos vacíos. Ante basura, devuelve fallback.
    """
    parsed = _extract_json_object(raw)
    if not parsed or not isinstance(parsed.get("months"), list):
        return fallback_skeleton()

    by_index: dict[int, dict] = {}
    for m in parsed["months"]:
        if not isinstance(m, dict):
            continue
        try:
            idx = int(m.get("month_index"))
        except (TypeError, ValueError):
            continue
        if not 1 <= idx <= 12:
            continue
        objectives = []
        for o in (m.get("objectives") or []):
            if not isinstance(o, dict) or not o.get("title"):
                continue
            objectives.append({
                "title": str(o["title"])[:300],
                "description": str(o["description"]) if o.get("description") else None,
                "kpi_refs": [str(k)[:120] for k in (o.get("kpi_refs") or []) if k][:5],
            })
        by_index[idx] = {
            "month_index": idx,
            "focus": str(m["focus"])[:300] if m.get("focus") else None,
            "objectives": objectives,
        }

    return [by_index.get(i, {"month_index": i, "focus": None, "objectives": []})
            for i in range(1, 13)]


def map_month_tasks(raw: str, objectives: list[dict], year: int, month: int) -> list[dict]:
    """
    Parsea las tareas de un mes. Descarta las que apunten a un objective_index inexistente.
    Retorna dicts con: objective_index, title, description, owner, priority, due_date(ISO),
    kpi_ref, tags, order_index.
    """
    parsed = _extract_json_object(raw)
    if not parsed or not isinstance(parsed.get("tasks"), list):
        return []

    out: list[dict] = []
    for order, t in enumerate(parsed["tasks"]):
        if not isinstance(t, dict) or not t.get("title"):
            continue
        try:
            obj_idx = int(t.get("objective_index", 0))
        except (TypeError, ValueError):
            continue
        if not 0 <= obj_idx < len(objectives):
            continue
        try:
            day = int(t.get("due_day", 28))
        except (TypeError, ValueError):
            day = 28
        out.append({
            "objective_index": obj_idx,
            "title": str(t["title"])[:200],
            "description": str(t["description"]) if t.get("description") else None,
            "owner": str(t["owner"]) if t.get("owner") else None,
            "priority": _norm_priority(t.get("priority")),
            "due_date": due_date_within_month(year, month, day).isoformat(),
            "kpi_ref": str(t["kpi_ref"])[:120] if t.get("kpi_ref") else None,
            "tags": _norm_tags(t.get("tags")),
            "order_index": order,
            **_norm_agenda_fields(t),
        })
    return out


def synthesize_diagnostico(agent_analyses: dict[str, dict]) -> str:
    """Concatena los summaries de los 4 agentes en un diagnóstico legible."""
    parts = []
    for agent, analysis in agent_analyses.items():
        if isinstance(analysis, dict) and analysis.get("summary"):
            parts.append(f"**{agent}:** {analysis['summary']}")
    return "\n\n".join(parts)


# ── Prompts ─────────────────────────────────────────────────────────────────

SKELETON_SYSTEM_PROMPT = load_prompt("agenda_anual_skeleton")  # editable en backend/prompts/agenda_anual_skeleton.md

SKELETON_SCHEMA = """{
  "months": [
    {"month_index": 1, "focus": "string",
     "objectives": [{"title": "string", "description": "string", "kpi_refs": ["KPI label"]}]}
  ]
}"""

MONTH_TASKS_SYSTEM_PROMPT = load_prompt("orden_del_dia_mes")  # editable en backend/prompts/orden_del_dia_mes.md

MONTH_TASKS_SCHEMA = """{
  "tasks": [
    {"objective_index": 0, "title": "string", "description": "string",
     "owner": "string", "lead_agent": "CFO|CSO|CRO|Auditor", "priority": "alta|media|baja", "due_day": 15,
     "kpi_ref": "KPI label|null", "required_doc": "string|null",
     "agenda_type": "informacion|seguimiento|deliberacion|decision",
     "decision_expected": "string|null", "tags": ["tag"]}
  ]
}"""


def _company_line(memory_buffer: dict) -> str:
    c = memory_buffer.get("company", {}) or {}
    return f"Empresa: {c.get('name', 'la empresa')} | Industria: {c.get('industry', 'N/D')}"


def _skeleton_vacio(months: list[dict]) -> bool:
    return all(not m.get("objectives") for m in months)


def generate_skeleton(memory_buffer: dict, diagnostico: str, kpi_labels: list[str]) -> list[dict]:
    """Paso 2: una llamada genera el esqueleto de 12 meses. Fallback si no hay API key.

    Si la respuesta llega ilegible/truncada (parse → 12 meses sin objetivos), reintenta una
    vez; si sigue vacía, LANZA para que el plan quede 'failed' (reintentable) en vez de
    completarse como un cascarón sin objetivos ni tareas."""
    if not settings.ANTHROPIC_API_KEY:
        return fallback_skeleton()

    user_prompt = (
        f"{_company_line(memory_buffer)}\n\n"
        f"DIAGNÓSTICO DE LOS 4 AGENTES:\n{diagnostico}\n\n"
        f"KPIs DISPONIBLES (usa solo estos labels en kpi_refs): {kpi_labels or 'ninguno'}\n\n"
        "Diseña el plan de 12 meses. Responde ÚNICAMENTE con JSON válido:\n"
        f"{SKELETON_SCHEMA}"
    )
    client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    for _ in range(2):
        response = _create_with_retry(
            client, model=settings.AI_MODEL, max_tokens=8192,
            system=SKELETON_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
        )
        skeleton = parse_skeleton(response.content[0].text)
        if not _skeleton_vacio(skeleton):
            return skeleton
    raise RuntimeError("El esqueleto del plan llegó vacío o ilegible tras 2 intentos.")


_MILESTONE_TYPES = {"trimestral", "semestral", "anual"}

MILESTONES_SYSTEM_PROMPT = load_prompt("milestones")  # editable en backend/prompts/milestones.md

MILESTONES_SCHEMA = """{
  "milestones": [
    {"type": "trimestral|semestral|anual", "year": 1, "period": 1,
     "title": "string", "target": "string", "kpi_ref": "KPI label|null"}
  ]
}"""


def parse_milestones(raw: str) -> dict:
    """Parsea hitos a {"items": [{type, year, period, title, target, kpi_ref}]}."""
    parsed = _extract_json_object(raw) or {}
    items = []
    for m in (parsed.get("milestones") or []):
        if not isinstance(m, dict) or m.get("type") not in _MILESTONE_TYPES or not m.get("title"):
            continue
        try:
            year = int(m.get("year", 1)); period = int(m.get("period", 1))
        except (TypeError, ValueError):
            continue
        items.append({
            "type": m["type"], "year": year, "period": period,
            "title": str(m["title"])[:200],
            "target": str(m.get("target") or "")[:300],
            "kpi_ref": str(m["kpi_ref"])[:120] if m.get("kpi_ref") else None,
        })
    return {"items": items}


def _milestones_vacio(milestones: dict) -> bool:
    return not (milestones or {}).get("items")


def generate_milestones(memory_buffer: dict, diagnostico: str, kpi_labels: list[str],
                        horizon_years: int) -> dict:
    """Paso 1: hitos del horizonte. Reintenta 1 vez; lanza si llega vacío (igual que el esqueleto)."""
    if not settings.ANTHROPIC_API_KEY:
        return {"items": []}
    user_prompt = (
        f"{_company_line(memory_buffer)}\n"
        f"HORIZONTE: {horizon_years} año(s).\n\n"
        f"DIAGNÓSTICO:\n{diagnostico}\n\n"
        f"VISIÓN A 3 AÑOS: {(memory_buffer.get('vision') or {}).get('statement', 'N/D')}\n\n"
        f"KPIs DISPONIBLES (usa solo estos labels): {kpi_labels or 'ninguno'}\n\n"
        f"Diseña los hitos. Responde ÚNICAMENTE con JSON válido:\n{MILESTONES_SCHEMA}"
    )
    client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    for _ in range(2):
        response = _create_with_retry(
            client, model=settings.AI_MODEL, max_tokens=4096,
            system=MILESTONES_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
        )
        milestones = parse_milestones(response.content[0].text)
        if not _milestones_vacio(milestones):
            return milestones
    raise RuntimeError("Los hitos del plan llegaron vacíos tras 2 intentos.")


def quarter_month_indices(year: int, quarter: int) -> list[int]:
    """Índices de mes GLOBALES (1-based) de los 3 meses de un (año, trimestre)."""
    base = (year - 1) * 12 + (quarter - 1) * 3
    return [base + 1, base + 2, base + 3]


QUARTER_SYSTEM_PROMPT = load_prompt("orden_del_dia_trimestre")  # editable en backend/prompts/orden_del_dia_trimestre.md

QUARTER_SCHEMA = """{
  "months": [
    {"month_in_quarter": 1, "focus": "string", "objectives": [
      {"title": "string", "description": "string", "kpi_refs": ["KPI label"], "tasks": [
        {"title": "string", "owner": "string", "lead_agent": "CFO|CSO|CRO|Auditor",
         "priority": "alta|media|baja", "kpi_ref": "KPI label|null", "required_doc": "string|null",
         "agenda_type": "informacion|seguimiento|deliberacion|decision",
         "decision_expected": "string|null", "due_day": 15}
      ]}
    ]}
  ]
}"""


def parse_quarter_plan(raw: str, year: int, quarter: int) -> list[dict]:
    """Parsea a EXACTAMENTE 3 meses (con month_index global), cada uno con objectives+tasks."""
    parsed = _extract_json_object(raw) or {}
    by_pos: dict[int, dict] = {}
    for m in (parsed.get("months") or []):
        if not isinstance(m, dict):
            continue
        try:
            pos = int(m.get("month_in_quarter"))
        except (TypeError, ValueError):
            continue
        if not 1 <= pos <= 3:
            continue
        objectives = []
        for o in (m.get("objectives") or []):
            if not isinstance(o, dict) or not o.get("title"):
                continue
            tasks = []
            for t in (o.get("tasks") or []):
                if not isinstance(t, dict) or not t.get("title"):
                    continue
                tasks.append({
                    "title": str(t["title"])[:200],
                    "description": str(t["description"]) if t.get("description") else None,
                    "owner": str(t["owner"]) if t.get("owner") else None,
                    "priority": _norm_priority(t.get("priority")),
                    "kpi_ref": str(t["kpi_ref"])[:120] if t.get("kpi_ref") else None,
                    "required_doc": str(t["required_doc"])[:200] if t.get("required_doc") else None,
                    "tags": _norm_tags(t.get("tags")),
                    "due_day": t.get("due_day", 28),
                    **_norm_agenda_fields(t),
                })
            objectives.append({
                "title": str(o["title"])[:300],
                "description": str(o["description"]) if o.get("description") else None,
                "kpi_refs": [str(k)[:120] for k in (o.get("kpi_refs") or []) if k][:5],
                "tasks": tasks,
            })
        by_pos[pos] = {"focus": str(m["focus"])[:300] if m.get("focus") else None,
                       "objectives": objectives}
    idxs = quarter_month_indices(year, quarter)
    return [{"month_index": idxs[p - 1], **by_pos.get(p, {"focus": None, "objectives": []})}
            for p in (1, 2, 3)]


def generate_quarter_plan(memory_buffer: dict, kpi_labels: list[str], milestones: dict,
                          year: int, quarter: int) -> list[dict]:
    """Paso 2: los 3 meses de un trimestre. Sin API key → 3 meses vacíos (no lanza)."""
    if not settings.ANTHROPIC_API_KEY:
        return parse_quarter_plan("", year, quarter)
    hitos_ctx = [m for m in (milestones or {}).get("items", [])
                 if m.get("year") == year and (m.get("type") != "trimestral" or m.get("period") == quarter)]
    user_prompt = (
        f"{_company_line(memory_buffer)}\n"
        f"AÑO {year}, TRIMESTRE {quarter}.\n"
        f"HITOS RELEVANTES: {hitos_ctx or 'ninguno'}\n"
        f"KPIs DISPONIBLES (usa solo estos labels): {kpi_labels or 'ninguno'}\n\n"
        f"Diseña los 3 meses del trimestre. Responde ÚNICAMENTE con JSON válido:\n{QUARTER_SCHEMA}"
    )
    client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    response = _create_with_retry(
        client, model=settings.AI_MODEL, max_tokens=4096,
        system=QUARTER_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_prompt}],
    )
    return parse_quarter_plan(response.content[0].text, year, quarter)


def generate_month_tasks(focus, objectives: list[dict], memory_buffer: dict,
                         year: int, month: int) -> list[dict]:
    """Paso 3: tareas de un mes. Sin API key u objetivos vacíos → []."""
    if not settings.ANTHROPIC_API_KEY or not objectives:
        return []

    obj_list = "\n".join(
        f"  [{i}] {o['title']} (KPIs: {o.get('kpi_refs') or 'ninguno'})"
        for i, o in enumerate(objectives)
    )
    user_prompt = (
        f"{_company_line(memory_buffer)}\n\n"
        f"FOCO DEL MES: {focus or 'N/D'}\n"
        f"OBJETIVOS DEL MES (usa el índice en objective_index):\n{obj_list}\n\n"
        "Genera las tareas. Responde ÚNICAMENTE con JSON válido:\n"
        f"{MONTH_TASKS_SCHEMA}"
    )
    client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    response = _create_with_retry(
        client, model=settings.AI_MODEL, max_tokens=2048,
        system=MONTH_TASKS_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_prompt}],
    )
    return map_month_tasks(response.content[0].text, objectives, year, month)
