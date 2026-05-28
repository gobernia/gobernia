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
