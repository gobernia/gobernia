"""
Revisión de fin de mes (subproyecto E).

- compute_signals: señales objetivas del mes (tareas + KPIs), puro/testeable.
- deterministic_review: review sin IA (fallback) — grade por % de cumplimiento.
- parse_review: normaliza la respuesta del LLM.
- run_month_review: una llamada estructurada al "consejo" (4 agentes + Challenger).
"""
from datetime import date

from app.core.config import settings
from app.services.ai.agents.base import _create_with_retry, _extract_json_object
from app.services.ai.kpi_engine import build_kpi_templates, _run_alert_rules

VALID_GRADES = {"bien", "mal", "muy_mal"}
VALID_PROPOSAL_TYPES = {"carry_over_task", "new_objective", "new_task"}


def compute_signals(tasks, kpi_values: dict, memory_buffer: dict, today: date) -> dict:
    """
    Señales del mes. `tasks` = iterable de objetos con .status y .due_date (date|None).
    `kpi_values` = {label: valor}. Usa kpi_engine para target/on_track por label.
    """
    tasks = list(tasks)
    total = len(tasks)
    completed = sum(1 for t in tasks if t.status == "completada")
    overdue = sum(
        1 for t in tasks
        if t.status != "completada" and t.due_date is not None and t.due_date < today
    )
    pct = round(completed / total * 100) if total else 0

    templates = {t.label.lower(): t for t in build_kpi_templates(memory_buffer)}
    kpis = []
    for label, value in (kpi_values or {}).items():
        tmpl = templates.get(str(label).lower())
        target = tmpl.benchmark if tmpl else None
        unit = tmpl.unit if tmpl else None
        on_track = None
        if tmpl is not None and value is not None:
            try:
                alert, _ = _run_alert_rules(tmpl, float(value))
                on_track = alert is None
            except (TypeError, ValueError):
                on_track = None
        kpis.append({
            "label": str(label), "value": value,
            "target": target, "unit": unit, "on_track": on_track,
        })

    return {
        "tasks_total": total, "tasks_completed": completed,
        "tasks_overdue": overdue, "completion_pct": pct, "kpis": kpis,
    }


def deterministic_review(signals: dict, incomplete_task_ids: list[str]) -> dict:
    """Review sin IA: grade por % de cumplimiento + arrastre de tareas incompletas."""
    pct = signals.get("completion_pct", 0)
    grade = "bien" if pct >= 80 else ("mal" if pct >= 50 else "muy_mal")
    proposals = [
        {"type": "carry_over_task", "task_id": tid,
         "reason": "Tarea no completada el mes anterior."}
        for tid in incomplete_task_ids
    ]
    return {
        "grade": grade,
        "summary": "Revisión automática basada en el cumplimiento de tareas del mes.",
        "by_agent": {},
        "proposals": proposals,
    }


def _norm_priority(v) -> str:
    return v.lower() if isinstance(v, str) and v.lower() in {"alta", "media", "baja"} else "media"


def _normalize_proposal(p: dict) -> dict | None:
    """Valida una propuesta del LLM. Devuelve dict limpio o None si es inválida."""
    if not isinstance(p, dict):
        return None
    t = p.get("type")
    if t not in VALID_PROPOSAL_TYPES:
        return None
    reason = str(p.get("reason", ""))[:300]
    if t == "carry_over_task":
        if not p.get("task_id"):
            return None
        return {"type": t, "task_id": str(p["task_id"]), "reason": reason}
    if t == "new_objective":
        if not p.get("title"):
            return None
        return {
            "type": t, "title": str(p["title"])[:300],
            "description": str(p["description"]) if p.get("description") else None,
            "kpi_refs": [str(k)[:120] for k in (p.get("kpi_refs") or []) if k][:5],
            "reason": reason,
        }
    # new_task
    if not p.get("title") or not p.get("objective_id"):
        return None
    return {
        "type": t, "objective_id": str(p["objective_id"]),
        "title": str(p["title"])[:200],
        "owner": str(p["owner"]) if p.get("owner") else None,
        "priority": _norm_priority(p.get("priority")),
        "kpi_ref": str(p["kpi_ref"])[:120] if p.get("kpi_ref") else None,
        "reason": reason,
    }


def parse_review(raw: str, fallback_grade: str) -> dict:
    """Normaliza la respuesta del LLM a {grade, summary, by_agent, proposals}."""
    parsed = _extract_json_object(raw)
    if not parsed:
        return {"grade": fallback_grade, "summary": "", "by_agent": {}, "proposals": []}
    grade = parsed.get("grade")
    if grade not in VALID_GRADES:
        grade = fallback_grade
    by_agent = parsed.get("by_agent")
    if not isinstance(by_agent, dict):
        by_agent = {}
    proposals = []
    for p in (parsed.get("proposals") or []):
        norm = _normalize_proposal(p)
        if norm is not None:
            proposals.append(norm)
    return {
        "grade": grade,
        "summary": str(parsed.get("summary", "")),
        "by_agent": {str(k): str(v) for k, v in by_agent.items()},
        "proposals": proposals,
    }
