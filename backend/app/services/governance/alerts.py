"""Alertas sobrias del Consejo (Bloque B6). Determinista, sin DB. Tono factual."""
from datetime import date, timedelta

_ORDER = {"critical": 0, "warning": 1, "info": 2}


def _plural(n: int) -> str:
    return "s" if n != 1 else ""


def review_alert(months) -> dict | None:
    """Alerta info cuando el mes 'done' más reciente tiene propuestas del Secretario sin aplicar."""
    done = [m for m in months if getattr(m, "status", None) == "done" and getattr(m, "review", None)]
    if not done:
        return None
    latest = max(done, key=lambda m: getattr(m, "month_index", 0))
    pending = [p for p in ((latest.review or {}).get("proposals") or []) if not p.get("applied")]
    if not pending:
        return None
    n = len(pending)
    return {
        "level": "info", "category": "revision",
        "message": f"El Secretario revisó tu mes: {n} propuesta{'s' if n != 1 else ''} para tu plan.",
    }


def compute_alerts(tasks, coverage_rows, kpi_signals, today: date, horizon_days: int = 7) -> list[dict]:
    alerts: list[dict] = []

    overdue = [
        t for t in tasks
        if t.status != "completada" and t.due_date is not None and t.due_date < today
    ]
    if overdue:
        n = len(overdue)
        alerts.append({
            "level": "critical", "category": "acuerdo",
            "message": f"{n} acuerdo{_plural(n)} vencido{_plural(n)} sin validar.",
        })

    upcoming = [
        t for t in tasks
        if t.status != "completada" and t.due_date is not None
        and today <= t.due_date <= today + timedelta(days=horizon_days)
    ]
    if upcoming:
        n = len(upcoming)
        verbo = "vence" if n == 1 else "vencen"
        alerts.append({
            "level": "warning", "category": "acuerdo",
            "message": f"{n} acuerdo{_plural(n)} {verbo} en los próximos {horizon_days} días.",
        })

    for r in coverage_rows or []:
        if r["estado"] == "critico":
            alerts.append({
                "level": "critical", "category": "cobertura",
                "message": f"{r['label']}: {r['realizadas']} de {r['esperadas']} revisiones — Crítico.",
            })
        elif r["estado"] == "atrasado":
            alerts.append({
                "level": "warning", "category": "cobertura",
                "message": f"{r['label']}: {r['realizadas']} de {r['esperadas']} revisiones — Atrasado.",
            })

    for k in kpi_signals or []:
        if k.get("on_track") is False:
            unit = k.get("unit") or ""
            target = k.get("target")
            meta = f" (meta {target}{unit})" if target is not None else ""
            alerts.append({
                "level": "warning", "category": "kpi",
                "message": f"{k.get('label')}: {k.get('value')}{unit}{meta} — fuera de objetivo.",
            })

    alerts.sort(key=lambda a: _ORDER.get(a["level"], 3))  # estable: críticos primero
    return alerts
