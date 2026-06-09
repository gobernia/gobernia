"""Motor de Orden del Día por señales (nodo 4, V1 determinista). Sin DB, sin IA.

Fusiona temas de cobertura programados + señales (KPI desviado, acuerdos vencidos/por
vencer) en una agenda priorizada de hasta `max_items` temas, cada uno con racional y
evidencia. Construye sobre coverage_rows (B4) y las señales del último cierre (B6/E).
"""
from datetime import date, timedelta


def _plural(n: int) -> str:
    return "s" if n != 1 else ""


def _impacto(score: float) -> str:
    if score >= 25:
        return "alto"
    if score >= 15:
        return "medio"
    return "bajo"


def build_agenda(scheduled_themes, coverage_rows, kpi_signals, tasks, today: date,
                 max_items: int = 7, horizon_days: int = 7) -> list[dict]:
    cov = {r["key"]: r for r in (coverage_rows or [])}
    candidatos: list[dict] = []

    # 1. DesviaciónKPI — un candidato por KPI fuera de objetivo
    for k in (kpi_signals or []):
        if k.get("on_track") is False:
            unit = k.get("unit") or ""
            target = k.get("target")
            meta = f" (meta {target}{unit})" if target is not None else ""
            candidatos.append({
                "titulo": f"Revisar {k.get('label')}: fuera de objetivo",
                "area": "kpi", "detector": "DesviaciónKPI",
                "urgencia": "media", "score": 30.0,
                "racional": f"Entra porque {k.get('label')} está fuera de objetivo.",
                "evidencia": [f"{k.get('label')}: {k.get('value')}{unit}{meta}"],
            })

    # 2. CompromisoVencido — un candidato agregado
    vencidos = [
        t for t in tasks
        if t.status != "completada" and t.due_date is not None and t.due_date < today
    ]
    if vencidos:
        n = len(vencidos)
        candidatos.append({
            "titulo": f"{n} acuerdo{_plural(n)} vencido{_plural(n)} sin validar",
            "area": "acuerdo", "detector": "CompromisoVencido",
            "urgencia": "alta", "score": 20.0 + 10.0 * min(n - 1, 2),
            "racional": f"Entra porque hay {n} acuerdo{_plural(n)} vencido{_plural(n)} sin validar.",
            "evidencia": [f"{t.title} (venció {t.due_date.isoformat()})" for t in vencidos[:3]],
        })

    # 3. CompromisoPorVencer — un candidato agregado
    horizonte = today + timedelta(days=horizon_days)
    porvencer = [
        t for t in tasks
        if t.status != "completada" and t.due_date is not None and today <= t.due_date <= horizonte
    ]
    if porvencer:
        n = len(porvencer)
        verbo = "vence" if n == 1 else "vencen"
        candidatos.append({
            "titulo": f"{n} acuerdo{_plural(n)} {verbo} esta semana",
            "area": "acuerdo", "detector": "CompromisoPorVencer",
            "urgencia": "media", "score": 10.0 + 5.0 * min(n - 1, 2),
            "racional": f"Entra porque {n} acuerdo{_plural(n)} {verbo} en los próximos {horizon_days} días.",
            "evidencia": [f"{t.title} (vence {t.due_date.isoformat()})" for t in porvencer[:3]],
        })

    # 4. TemaDeCobertura — un candidato por tema programado del mes
    for t in scheduled_themes:
        row = cov.get(t.key, {})
        estado = row.get("estado", "en_tiempo")
        boost = 20.0 if estado == "critico" else (10.0 if estado == "atrasado" else 0.0)
        urg = "alta" if estado == "critico" else ("media" if estado == "atrasado" else "baja")
        if estado in ("atrasado", "critico"):
            real, esp = row.get("realizadas", 0), row.get("esperadas", 0)
            evidencia = [f"{t.label}: {real} de {esp} revisiones — {estado.capitalize()}"]
            racional = f"Entra porque toca cubrir {t.label} este mes y va atrasado ({real}/{esp})."
        else:
            evidencia = ["Programado para esta sesión."]
            racional = f"Entra porque toca cubrir {t.label} este mes."
        candidatos.append({
            "titulo": f"Cubrir: {t.label}",
            "area": "cobertura", "detector": "TemaDeCobertura",
            "urgencia": urg, "score": 10.0 + boost,
            "racional": racional, "evidencia": evidencia,
        })

    candidatos.sort(key=lambda c: c["score"], reverse=True)  # estable: respeta orden de inserción
    agenda: list[dict] = []
    for i, c in enumerate(candidatos[:max_items], start=1):
        agenda.append({
            "orden": i, "titulo": c["titulo"], "area": c["area"], "detector": c["detector"],
            "impacto": _impacto(c["score"]), "urgencia": c["urgencia"],
            "racional": c["racional"], "evidencia": c["evidencia"], "score": c["score"],
        })
    return agenda
