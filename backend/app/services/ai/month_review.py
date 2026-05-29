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
