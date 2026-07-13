"""
Revisión de fin de mes (subproyecto E).

- compute_signals: señales objetivas del mes (tareas + KPIs), puro/testeable.
- deterministic_review: review sin IA (fallback) — grade por % de cumplimiento.
- parse_review: normaliza la respuesta del LLM.
- run_month_review: una llamada estructurada al "consejo" (4 agentes + Challenger).
"""
import json
from datetime import date

import anthropic

from app.core.config import settings
from app.services.ai.agents.base import _create_with_retry, _extract_json_object
from app.services.ai.doc_blocks import build_doc_blocks, readable_docs
from app.services.ai.kpi_engine import build_kpi_templates, _run_alert_rules

VALID_GRADES = {"bien", "mal", "muy_mal"}
VALID_PROPOSAL_TYPES = {"carry_over_task", "new_objective", "new_task"}

_MAX_REVIEW_DOCS = 8


def compute_signals(tasks, kpi_values: dict, memory_buffer: dict, today: date,
                    evidence_counts: dict | None = None) -> dict:
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

    tasks_missing_doc = []
    if evidence_counts is not None:
        ev = evidence_counts
        tasks_missing_doc = [
            {"title": getattr(t, "title", ""), "required_doc": t.required_doc}
            for t in tasks
            if getattr(t, "required_doc", None) and ev.get(str(t.id), 0) == 0
        ]

    return {
        "tasks_total": total, "tasks_completed": completed,
        "tasks_overdue": overdue, "completion_pct": pct, "kpis": kpis,
        "tasks_missing_doc": tasks_missing_doc,
    }


def deterministic_review(signals: dict, incomplete_task_ids: list[str]) -> dict:
    """Review sin IA: grade por % de cumplimiento + arrastre de tareas incompletas."""
    pct = signals.get("completion_pct", 0)
    grade = "bien" if pct >= 80 else ("mal" if pct >= 50 else "muy_mal")
    missing = signals.get("tasks_missing_doc") or []
    summary = "Revisión automática basada en el cumplimiento de tareas del mes."
    if missing:
        n = len(missing)
        summary += f" {n} tarea{'s' if n != 1 else ''} sin su documento de sustento — súbelos para validarlas."
    proposals = [
        {"type": "carry_over_task", "task_id": tid,
         "reason": "Tarea no completada el mes anterior."}
        for tid in incomplete_task_ids
    ]
    return {
        "grade": grade,
        "summary": summary,
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


REVIEW_SYSTEM_PROMPT = """Eres el consejo de administración de Gobernia revisando el cierre de un mes
del plan estratégico. Lo integran CFO, CSO, CRO y Auditor, y un Challenger que cuestiona.

Con base en las SEÑALES del mes (cumplimiento de tareas y avance de KPIs) y el contexto de la
empresa, emite un veredicto honesto y accionable. El Challenger te obliga a no ser complaciente:
si el avance es pobre, dilo claro.

Reglas:
1. "grade": "bien" si el mes va sólido, "mal" si hay desviaciones importantes, "muy_mal" si el
   avance es crítico. Sé congruente con las señales (un completion_pct bajo no puede ser "bien").
2. "summary": 2-4 oraciones dirigidas al dueño, claras y directas ("vas bien/mal/muy mal" + por qué).
3. "by_agent": una línea breve por agente (CFO, CSO, CRO, Auditor) con su lectura del mes.
4. "proposals": ajustes CONCRETOS al mes SIGUIENTE. Tipos válidos:
   - {"type":"carry_over_task","task_id":"<id>","reason":"..."} para arrastrar una tarea incompleta.
   - {"type":"new_objective","title":"...","description":"...","kpi_refs":["..."],"reason":"..."}.
   - {"type":"new_task","objective_id":"<id de un objetivo del mes siguiente>","title":"...",
      "owner":"...","priority":"alta|media|baja","kpi_ref":"...","reason":"..."}.
   Propón entre 1 y 5 cambios, los más importantes. No inventes ids de tareas que no estén en la lista.
5. Si 'tasks_missing_doc' del JSON de señales trae tareas, esas NO pueden considerarse logradas
   sin su documento de sustento: dilo en el summary, pésalo en el grade, y propón subir el
   documento (o arrastra la tarea con carry_over_task).
6. Si se adjuntan DOCUMENTOS (PDF/imágenes), son las evidencias subidas este mes. Cada uno trae
   antes un texto que dice de qué tarea es y qué pedía. Léelos y valida si CADA documento respalda
   la meta de su tarea: si no la respalda, no des la tarea por lograda — propón arrastrarla
   (carry_over_task) o ajustarla, y dilo en el summary. NO inventes contenido de documentos que no
   se adjuntaron. Si hay una NOTA SOBRE DOCUMENTOS, menciónala (p. ej. pídele al usuario subir en
   PDF los formatos que no se pudieron leer)."""

REVIEW_SCHEMA = """{
  "grade": "bien|mal|muy_mal",
  "summary": "string",
  "by_agent": {"CFO": "string", "CSO": "string", "CRO": "string", "Auditor": "string"},
  "proposals": [{"type": "carry_over_task|new_objective|new_task", "...": "..."}]
}"""


def select_review_documents(evidences, tasks_by_id: dict, max_docs: int = _MAX_REVIEW_DOCS):
    """De las evidencias del mes, selecciona las legibles (PDF/imagen), las más recientes hasta
    max_docs, con un label por documento. Devuelve (seleccionados, nota_texto). No descarga nada."""
    evs = sorted(evidences, key=lambda e: e.created_at, reverse=True)
    candidates: list[dict] = []
    for e in evs:
        task = tasks_by_id.get(str(e.action_task_id))
        label = f"Documento «{e.filename}»"
        if task is not None:
            label += f" de la tarea «{getattr(task, 'title', '')}»"
            if getattr(task, "required_doc", None):
                label += f" que pedía: {task.required_doc}"
        candidates.append({"s3_key": e.s3_key, "filename": e.filename, "label": label})

    selected, note = readable_docs(candidates, max_docs=max_docs)
    return [
        {"s3_key": d["s3_key"], "kind": d["kind"], "media_type": d["media_type"], "label": d["label"]}
        for d in selected
    ], note


def _build_review_content(user_prompt: str, documents: list[dict] | None):
    """Sin documentos → string (comportamiento de hoy). Con documentos → lista de bloques multimodales."""
    if not documents:
        return user_prompt
    return build_doc_blocks(documents) + [{"type": "text", "text": user_prompt}]


def run_month_review(signals: dict, month_focus, objectives: list[dict],
                     memory_buffer: dict, period_label: str,
                     incomplete_task_ids: list[str],
                     documents: list[dict] | None = None,
                     documents_note: str = "") -> dict:
    """Una llamada estructurada al consejo. Sin API key → review determinista."""
    if not settings.ANTHROPIC_API_KEY:
        return deterministic_review(signals, incomplete_task_ids)

    fallback_grade = deterministic_review(signals, incomplete_task_ids)["grade"]

    from app.services.ai.agents.base import _build_company_context
    company_ctx = _build_company_context(memory_buffer)
    obj_lines = "\n".join(f"  - {o.get('title','')}" for o in objectives) or "  (sin objetivos)"
    incomplete = ", ".join(incomplete_task_ids) or "ninguna"

    nota_docs = f"NOTA SOBRE DOCUMENTOS: {documents_note}\n" if documents_note else ""
    user_prompt = (
        f"EMPRESA:\n{company_ctx}\n\n"
        f"MES: {period_label} | Foco: {month_focus or 'N/D'}\n"
        f"OBJETIVOS DEL MES:\n{obj_lines}\n\n"
        f"SEÑALES DEL MES:\n{json.dumps(signals, ensure_ascii=False, indent=2)}\n"
        f"IDs de tareas incompletas (para carry_over_task): {incomplete}\n"
        f"{nota_docs}\n"
        "Emite el veredicto del consejo. Responde ÚNICAMENTE con JSON válido:\n"
        f"{REVIEW_SCHEMA}"
    )
    client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    response = _create_with_retry(
        client, model=settings.AI_MODEL, max_tokens=2048,
        system=REVIEW_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": _build_review_content(user_prompt, documents)}],
    )
    return parse_review(response.content[0].text, fallback_grade=fallback_grade)
