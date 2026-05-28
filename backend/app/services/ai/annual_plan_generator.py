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


# ── Helpers de calendario ───────────────────────────────────────────────────

def month_calendar(start_year: int, start_month: int, month_index: int) -> tuple[int, int]:
    """Dado el mes de inicio y un month_index 1..12, retorna (año, mes) calendario."""
    zero_based = (start_year * 12 + (start_month - 1)) + (month_index - 1)
    return zero_based // 12, zero_based % 12 + 1


def compute_active_month_index(start_date: date, today: date) -> int:
    """Índice (1..12) del mes vigente del plan según la fecha de hoy. Cap en [1, 12]."""
    elapsed = (today.year - start_date.year) * 12 + (today.month - start_date.month)
    return min(max(elapsed + 1, 1), 12)


def due_date_within_month(year: int, month: int, day: int = 28) -> date:
    """Construye una fecha dentro del mes, clampeando el día a [1, último día del mes]."""
    last = calendar.monthrange(year, month)[1]
    return date(year, month, min(max(day, 1), last))


# ── Normalización ───────────────────────────────────────────────────────────

_PRIORITIES = {"alta", "media", "baja"}


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
        })
    return out


def synthesize_diagnostico(agent_analyses: dict[str, dict]) -> str:
    """Concatena los summaries de los 4 agentes en un diagnóstico legible."""
    parts = []
    for agent, analysis in agent_analyses.items():
        if isinstance(analysis, dict) and analysis.get("summary"):
            parts.append(f"**{agent}:** {analysis['summary']}")
    return "\n\n".join(parts)
