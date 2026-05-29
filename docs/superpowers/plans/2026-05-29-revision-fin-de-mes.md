# Revisión de fin de mes (Subproyecto E) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Cierre manual de mes que captura KPIs, hace que el consejo (4 agentes + Challenger, en una llamada estructurada) califique el avance (bien/mal/muy_mal) y proponga ajustes al mes siguiente que el usuario aprueba uno por uno.

**Architecture:** Lógica pura y testeable (`compute_signals`, `parse_review`, `deterministic_review`) + una llamada LLM síncrona (`run_month_review`) en `app/services/ai/month_review.py`. Endpoints `close` y `apply-proposal` en el router del plan anual, reutilizando el patrón síncrono de `/analyse` (`anyio.to_thread` + reabrir sesión para persistir). Resultado en `MonthlyPlan.review` (JSONB ya reservado, sin migración). Frontend extiende `/dashboard/plan`.

**Tech Stack:** FastAPI, SQLAlchemy async, Anthropic SDK, kpi_engine existente, pytest; Next.js 16 + TS + framer-motion (frontend).

**Spec:** `docs/superpowers/specs/2026-05-29-revision-fin-de-mes-design.md`
**Rama:** `feat/plan-12-meses-revision-mensual` (apilada sobre `feat/plan-12-meses-frontend`).

---

## Notas de entorno

- Backend desde `backend/`: intérprete `venv/bin/python`, tests `venv/bin/pytest` (pytest.ini `asyncio_mode=auto`). Frontend desde `frontend/`: gate `npx tsc --noEmit` (no hay framework de tests; hay errores de lint PREEXISTENTES en `onboarding/etapa-5` y `etapa-7` — ignorar).
- `@/lib/api` ya inyecta el token (con el fix de carrera de token de la rama base). Rutas relativas.
- `kpi_engine` (`app/services/ai/kpi_engine.py`) expone `build_kpi_templates(memory_buffer) -> list[KPITemplate]` y `_run_alert_rules(template, value) -> (alert|None, msg|None)`. `KPITemplate` tiene `.label`, `.benchmark` (float|None), `.unit`. Si un KPI no dispara alerta, está "en rumbo".
- Agentes: `agents/base.py` tiene `_create_with_retry`, `_extract_json_object`, `_build_company_context`. La generación de plan ya usa `anyio.to_thread` en `/analyse` — replicar ese patrón.
- `MonthlyPlanOut` (en `app/schemas/annual_plan.py`) ya incluye `review: dict | None`.

---

## Estructura de archivos

**Crear:**
- `backend/app/services/ai/month_review.py` — `compute_signals`, `deterministic_review`, `parse_review`, prompts + `run_month_review`.
- `backend/tests/unit/test_month_review.py` — tests de la lógica pura + LLM mockeado.
- `backend/tests/integration/test_month_close_api.py` — tests de los endpoints.
- `frontend/src/components/plan/CloseMonthModal.tsx` — captura de KPIs + dispara cierre.
- `frontend/src/components/plan/MonthReviewPanel.tsx` — calificación + resumen + propuestas.

**Modificar:**
- `backend/app/schemas/annual_plan.py` — `CloseMonthRequest`, `ApplyProposalRequest`, `CloseMonthResponse`.
- `backend/app/api/v1/annual_plan/router.py` — endpoints `close` y `apply-proposal`.
- `frontend/src/lib/annualPlan.ts` — tipos `MonthReview`/`Proposal` + `closeMonth`, `applyProposal`.
- `frontend/src/components/plan/MonthDetail.tsx` — botón "Cerrar mes y revisar" + render del review.
- `frontend/src/components/plan/MonthTimeline.tsx` — indicador de calificación en meses cerrados.
- `frontend/src/app/dashboard/plan/page.tsx` — estado del modal, handlers `onCloseMonth`/`onApplyProposal`.

---

## Task 1: Schemas Pydantic

**Files:**
- Modify: `backend/app/schemas/annual_plan.py`
- Test: `backend/tests/unit/test_month_review.py` (primer test)

- [ ] **Step 1: Escribir el test (falla)** — crea `backend/tests/unit/test_month_review.py`:

```python
from app.schemas.annual_plan import CloseMonthRequest, ApplyProposalRequest


def test_close_request_kpis_default_empty():
    r = CloseMonthRequest()
    assert r.kpis == {}
    r2 = CloseMonthRequest(kpis={"Razón corriente": 1.2})
    assert r2.kpis["Razón corriente"] == 1.2


def test_apply_proposal_request():
    a = ApplyProposalRequest(proposal_id="abc")
    assert a.proposal_id == "abc"
```

- [ ] **Step 2: Correr (falla)**

Run: `venv/bin/pytest tests/unit/test_month_review.py -v`
Expected: FAIL con `ImportError: cannot import name 'CloseMonthRequest'`.

- [ ] **Step 3: Agregar a `app/schemas/annual_plan.py`** (al final del archivo):

```python
class CloseMonthRequest(BaseModel):
    kpis: dict[str, float] = Field(default_factory=dict)


class ApplyProposalRequest(BaseModel):
    proposal_id: str


class CloseMonthResponse(BaseModel):
    month:              MonthlyPlanOut
    active_month_index: int
```

- [ ] **Step 4: Correr (pasa)**

Run: `venv/bin/pytest tests/unit/test_month_review.py -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add backend/app/schemas/annual_plan.py backend/tests/unit/test_month_review.py
git commit -m "feat(review): schemas de cierre de mes y aplicar propuesta"
```

---

## Task 2: `compute_signals` (lógica pura)

**Files:**
- Create: `backend/app/services/ai/month_review.py`
- Modify: `backend/tests/unit/test_month_review.py`

- [ ] **Step 1: Agregar tests (fallan)** — añade a `tests/unit/test_month_review.py`:

```python
from datetime import date
from types import SimpleNamespace
from app.services.ai.month_review import compute_signals


def _task(status, due):
    return SimpleNamespace(status=status, due_date=due)


def test_compute_signals_counts_and_pct():
    today = date(2026, 6, 15)
    tasks = [
        _task("completada", date(2026, 6, 10)),
        _task("pendiente", date(2026, 6, 1)),   # atrasada
        _task("en_progreso", date(2026, 6, 30)),
        _task("completada", None),
    ]
    s = compute_signals(tasks, {}, {"company": {}}, today)
    assert s["tasks_total"] == 4
    assert s["tasks_completed"] == 2
    assert s["tasks_overdue"] == 1
    assert s["completion_pct"] == 50


def test_compute_signals_kpi_on_track_via_engine():
    today = date(2026, 6, 15)
    # "Margen operativo" tiene benchmark 15% (mayor es mejor). 20 → en rumbo; 5 → no.
    buf = {"company": {"industry": "manufacturing", "employees": "11-50"}}
    s_ok = compute_signals([], {"Margen operativo": 20.0}, buf, today)
    s_bad = compute_signals([], {"Margen operativo": 5.0}, buf, today)
    assert s_ok["kpis"][0]["on_track"] is True
    assert s_bad["kpis"][0]["on_track"] is False
    assert s_ok["kpis"][0]["target"] == 15.0


def test_compute_signals_unknown_kpi_label():
    s = compute_signals([], {"KPI inventado": 1.0}, {"company": {}}, date(2026, 6, 1))
    k = s["kpis"][0]
    assert k["on_track"] is None and k["target"] is None
    assert k["value"] == 1.0
```

- [ ] **Step 2: Correr (falla)**

Run: `venv/bin/pytest tests/unit/test_month_review.py -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'app.services.ai.month_review'`.

- [ ] **Step 3: Crear `app/services/ai/month_review.py`** (primera parte):

```python
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
```

- [ ] **Step 4: Correr (pasa)**

Run: `venv/bin/pytest tests/unit/test_month_review.py -v`
Expected: PASS (5 tests en total). Nota: si `_run_alert_rules` para "Margen operativo" no marca alerta con 20 y sí con 5, los asserts pasan; si la dirección difiriera, ajustar el test al comportamiento real de `kpi_engine` (no el revés).

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/ai/month_review.py backend/tests/unit/test_month_review.py
git commit -m "feat(review): compute_signals (tareas + KPIs vía kpi_engine)"
```

---

## Task 3: `deterministic_review` + `parse_review`

**Files:**
- Modify: `backend/app/services/ai/month_review.py`
- Modify: `backend/tests/unit/test_month_review.py`

- [ ] **Step 1: Agregar tests (fallan)** — añade a `tests/unit/test_month_review.py`:

```python
from app.services.ai.month_review import deterministic_review, parse_review


def test_deterministic_review_grades_by_pct():
    assert deterministic_review({"completion_pct": 90}, [])["grade"] == "bien"
    assert deterministic_review({"completion_pct": 60}, [])["grade"] == "mal"
    assert deterministic_review({"completion_pct": 10}, [])["grade"] == "muy_mal"


def test_deterministic_review_carryover_proposals():
    r = deterministic_review({"completion_pct": 40}, ["t1", "t2"])
    types = [p["type"] for p in r["proposals"]]
    assert types == ["carry_over_task", "carry_over_task"]
    assert r["proposals"][0]["task_id"] == "t1"


def test_parse_review_clamps_grade_and_validates_proposals():
    raw = '''{"grade":"EXCELENTE","summary":"ok","by_agent":{"CFO":"bien"},
      "proposals":[
        {"type":"new_objective","title":"Mejorar caja","kpi_refs":["Razón corriente"]},
        {"type":"carry_over_task","task_id":"t1"},
        {"type":"basura"},
        {"type":"new_task","objective_id":"o1","title":"Hacer X","priority":"ALTA"}
      ]}'''
    out = parse_review(raw, fallback_grade="mal")
    assert out["grade"] == "mal"            # "EXCELENTE" no es válido → fallback
    assert out["summary"] == "ok"
    assert out["by_agent"]["CFO"] == "bien"
    kinds = [p["type"] for p in out["proposals"]]
    assert kinds == ["new_objective", "carry_over_task", "new_task"]   # "basura" descartada
    assert out["proposals"][2]["priority"] == "alta"   # normalizada


def test_parse_review_garbage_uses_fallback():
    out = parse_review("no json", fallback_grade="muy_mal")
    assert out["grade"] == "muy_mal"
    assert out["proposals"] == []
```

- [ ] **Step 2: Correr (falla)**

Run: `venv/bin/pytest tests/unit/test_month_review.py -v`
Expected: FAIL con `ImportError: cannot import name 'deterministic_review'`.

- [ ] **Step 3: Agregar a `month_review.py`**:

```python
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
```

- [ ] **Step 4: Correr (pasa)**

Run: `venv/bin/pytest tests/unit/test_month_review.py -v`
Expected: PASS (9 tests en total).

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/ai/month_review.py backend/tests/unit/test_month_review.py
git commit -m "feat(review): deterministic_review y parse_review con validación de propuestas"
```

---

## Task 4: `run_month_review` (llamada al consejo)

**Files:**
- Modify: `backend/app/services/ai/month_review.py`
- Modify: `backend/tests/unit/test_month_review.py`

- [ ] **Step 1: Agregar tests (fallan)** — añade a `tests/unit/test_month_review.py`:

```python
import app.services.ai.month_review as mr


class _Resp:
    def __init__(self, text): self.content = [type("B", (), {"text": text})()]


def test_run_month_review_sin_apikey_usa_determinista(monkeypatch):
    monkeypatch.setattr(mr.settings, "ANTHROPIC_API_KEY", "", raising=False)
    out = mr.run_month_review(
        signals={"completion_pct": 90, "tasks_total": 2, "tasks_completed": 2,
                 "tasks_overdue": 0, "kpis": []},
        month_focus="Liquidez", objectives=[], memory_buffer={"company": {}},
        period_label="Mayo 2026", incomplete_task_ids=[],
    )
    assert out["grade"] == "bien"           # 90% → bien (determinista)


def test_run_month_review_con_apikey_parsea(monkeypatch):
    monkeypatch.setattr(mr.settings, "ANTHROPIC_API_KEY", "sk-test", raising=False)
    raw = '{"grade":"mal","summary":"Vas regular","by_agent":{"CFO":"cuida la caja"},"proposals":[{"type":"carry_over_task","task_id":"t1"}]}'
    monkeypatch.setattr(mr, "_create_with_retry", lambda *a, **k: _Resp(raw))
    monkeypatch.setattr(mr.anthropic, "Anthropic", lambda **k: object())
    out = mr.run_month_review(
        signals={"completion_pct": 55, "tasks_total": 4, "tasks_completed": 2,
                 "tasks_overdue": 1, "kpis": []},
        month_focus="Liquidez", objectives=[{"title": "Mejorar caja"}],
        memory_buffer={"company": {"name": "Demo"}}, period_label="Mayo 2026",
        incomplete_task_ids=["t1"],
    )
    assert out["grade"] == "mal"
    assert out["summary"] == "Vas regular"
    assert out["proposals"][0]["type"] == "carry_over_task"
```

- [ ] **Step 2: Correr (falla)**

Run: `venv/bin/pytest tests/unit/test_month_review.py -v`
Expected: FAIL con `AttributeError: module ... has no attribute 'run_month_review'` (o `anthropic` no importado).

- [ ] **Step 3: Agregar a `month_review.py`** (import de anthropic arriba + la función):

Al inicio del archivo, junto a los imports, agrega:
```python
import json

import anthropic
```

Al final del archivo:
```python
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
   Propón entre 1 y 5 cambios, los más importantes. No inventes ids de tareas que no estén en la lista."""

REVIEW_SCHEMA = """{
  "grade": "bien|mal|muy_mal",
  "summary": "string",
  "by_agent": {"CFO": "string", "CSO": "string", "CRO": "string", "Auditor": "string"},
  "proposals": [{"type": "carry_over_task|new_objective|new_task", "...": "..."}]
}"""


def run_month_review(signals: dict, month_focus, objectives: list[dict],
                     memory_buffer: dict, period_label: str,
                     incomplete_task_ids: list[str]) -> dict:
    """Una llamada estructurada al consejo. Sin API key → review determinista."""
    fallback_grade = deterministic_review(signals, incomplete_task_ids)["grade"]
    if not settings.ANTHROPIC_API_KEY:
        return deterministic_review(signals, incomplete_task_ids)

    from app.services.ai.agents.base import _build_company_context
    company_ctx = _build_company_context(memory_buffer)
    obj_lines = "\n".join(f"  - {o.get('title','')}" for o in objectives) or "  (sin objetivos)"
    incomplete = ", ".join(incomplete_task_ids) or "ninguna"

    user_prompt = (
        f"EMPRESA:\n{company_ctx}\n\n"
        f"MES: {period_label} | Foco: {month_focus or 'N/D'}\n"
        f"OBJETIVOS DEL MES:\n{obj_lines}\n\n"
        f"SEÑALES DEL MES:\n{json.dumps(signals, ensure_ascii=False, indent=2)}\n"
        f"IDs de tareas incompletas (para carry_over_task): {incomplete}\n\n"
        "Emite el veredicto del consejo. Responde ÚNICAMENTE con JSON válido:\n"
        f"{REVIEW_SCHEMA}"
    )
    client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    response = _create_with_retry(
        client, model=settings.AI_MODEL, max_tokens=2048,
        system=REVIEW_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_prompt}],
    )
    return parse_review(response.content[0].text, fallback_grade=fallback_grade)
```

- [ ] **Step 4: Correr (pasa)**

Run: `venv/bin/pytest tests/unit/test_month_review.py -v`
Expected: PASS (11 tests en total).

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/ai/month_review.py backend/tests/unit/test_month_review.py
git commit -m "feat(review): run_month_review (llamada estructurada al consejo + fallback)"
```

---

## Task 5: Endpoints `close` y `apply-proposal`

**Files:**
- Modify: `backend/app/api/v1/annual_plan/router.py`
- Test: `backend/tests/integration/test_month_close_api.py`

- [ ] **Step 1: Escribir el test (falla)** — crea `backend/tests/integration/test_month_close_api.py`:

```python
"""Integración de cierre de mes y aplicar propuesta."""
import uuid
from datetime import date
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.core.dependencies import get_current_user_id, get_db
import app.api.v1.annual_plan.router as plan_router

MOCK_USER_ID = "user_test_close"


async def _user_override():
    return MOCK_USER_ID


@pytest.mark.asyncio
async def test_close_month_not_active_409(monkeypatch):
    month = MagicMock()
    month.status = "locked"
    monkeypatch.setattr(plan_router, "_load_owned_month",
                        AsyncMock(return_value=month))

    async def override_db():
        db = AsyncMock(); db.commit = AsyncMock(); yield db
    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user_id] = _user_override
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.post("/api/v1/annual-plan/months/3/close", json={"kpis": {}})
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 409


@pytest.mark.asyncio
async def test_close_month_runs_review(monkeypatch):
    active_month = MagicMock()
    active_month.status = "active"
    monkeypatch.setattr(plan_router, "_load_owned_month",
                        AsyncMock(return_value=active_month))
    monkeypatch.setattr(
        plan_router, "_run_close",
        AsyncMock(return_value={"month_index": 1, "active_month_index": 2,
                                "grade": "bien"}))

    async def override_db():
        db = AsyncMock(); yield db
    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user_id] = _user_override
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.post("/api/v1/annual-plan/months/1/close", json={"kpis": {"Razón corriente": 1.2}})
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 200
    assert r.json()["grade"] == "bien"
```

> Nota de diseño para testabilidad: el endpoint delega en helpers `_load_owned_month` y `_run_close` para poder mockearlos. Los tests del flujo real (agentes, persistencia) ya están cubiertos por los unit tests de `month_review`; aquí se prueban routing y el guard 409.

- [ ] **Step 2: Correr (falla)**

Run: `venv/bin/pytest tests/integration/test_month_close_api.py -v`
Expected: FAIL (404/AttributeError — endpoints/helpers no existen).

- [ ] **Step 3: Agregar al final de `app/api/v1/annual_plan/router.py`**:

Primero, en los imports del archivo agrega:
```python
import anyio
from datetime import date
from app.schemas.annual_plan import CloseMonthRequest, ApplyProposalRequest
from app.services.ai.month_review import compute_signals, run_month_review
from app.services.ai.agents.base import _MONTH_NAMES
```
(Si `date` ya está importado, no lo dupliques. `_MONTH_NAMES` es la lista `["", "Enero", … "Diciembre"]` definida en `agents/base.py`.)

Luego, al final del archivo:
```python
# ── Cierre de mes / revisión ──────────────────────────────────────────────────

async def _load_owned_month(month_index: int, user_id: str, db: AsyncSession) -> MonthlyPlan | None:
    plan = await _current_plan(user_id, db)
    if not plan:
        return None
    res = await db.execute(
        select(MonthlyPlan)
        .where(MonthlyPlan.annual_plan_id == plan.id, MonthlyPlan.month_index == month_index)
        .options(selectinload(MonthlyPlan.objectives))
    )
    return res.scalar_one_or_none()


async def _run_close(month: MonthlyPlan, kpis: dict, user_id: str) -> dict:
    """
    Corre la revisión y persiste en una sesión nueva (patrón /analyse: los agentes
    corren fuera de la conexión de la request). Devuelve dict con grade + índices.
    """
    from app.db.session import AsyncSessionLocal
    from sqlalchemy.orm.attributes import flag_modified
    from app.models.onboarding_session import OnboardingSession

    today = date.today()
    obj_ids = [o.id for o in month.objectives]
    month_id = month.id
    month_index = month.month_index
    annual_plan_id = month.annual_plan_id
    focus = month.focus

    # Cargar tareas del mes y memory_buffer; snapshot y cerrar conexión antes del LLM.
    async with AsyncSessionLocal() as db:
        tasks = []
        if obj_ids:
            res = await db.execute(select(ActionTask).where(ActionTask.objective_id.in_(obj_ids)))
            tasks = list(res.scalars().all())
        onb = await db.execute(
            select(OnboardingSession).where(OnboardingSession.user_id == user_id)
            .order_by(OnboardingSession.created_at.desc()).limit(1)
        )
        onboarding = onb.scalar_one_or_none()
        memory_buffer = (onboarding.memory_buffer if onboarding else {}) or {}
        objectives = [{"title": o.title} for o in month.objectives]

    incomplete_ids = [str(t.id) for t in tasks if t.status != "completada"]
    signals = compute_signals(tasks, kpis, memory_buffer, today)
    period_label = f"{_MONTH_NAMES[month.period_month]} {month.period_year}"

    review = await anyio.to_thread.run_sync(
        lambda: run_month_review(
            signals=signals, month_focus=focus,
            objectives=objectives, memory_buffer=memory_buffer,
            period_label=period_label, incomplete_task_ids=incomplete_ids,
        )
    )
    review["closed_at"] = today.isoformat()
    review["signals"] = signals
    for p in review["proposals"]:
        p["id"] = str(uuid.uuid4())
        p["applied"] = False

    # Persistir: marcar mes done, siguiente active.
    async with AsyncSessionLocal() as db:
        m = await db.get(MonthlyPlan, month_id)
        m.review = review
        m.status = "done"
        flag_modified(m, "review")
        nxt = await db.execute(
            select(MonthlyPlan).where(
                MonthlyPlan.annual_plan_id == annual_plan_id,
                MonthlyPlan.month_index == month_index + 1,
            )
        )
        nxt_m = nxt.scalar_one_or_none()
        if nxt_m is not None and nxt_m.status == "locked":
            nxt_m.status = "active"
        await db.commit()

    active_idx = month_index + 1 if month_index < 12 else month_index
    return {"month_index": month_index, "active_month_index": active_idx, "grade": review["grade"]}


@router.post("/annual-plan/months/{month_index}/close")
async def close_month(
    month_index: int,
    body: CloseMonthRequest,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    month = await _load_owned_month(month_index, user_id, db)
    if month is None:
        raise HTTPException(status_code=404, detail="Mes no encontrado.")
    if month.status != "active":
        raise HTTPException(status_code=409, detail="Solo puedes cerrar el mes activo.")
    result = await _run_close(month, body.kpis, user_id)
    return result


@router.post("/annual-plan/months/{month_index}/apply-proposal")
async def apply_proposal(
    month_index: int,
    body: ApplyProposalRequest,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    from sqlalchemy.orm.attributes import flag_modified
    month = await _load_owned_month(month_index, user_id, db)
    if month is None or not month.review:
        raise HTTPException(status_code=404, detail="Mes o revisión no encontrada.")

    review = dict(month.review)
    proposals = review.get("proposals", [])
    prop = next((p for p in proposals if p.get("id") == body.proposal_id), None)
    if prop is None:
        raise HTTPException(status_code=404, detail="Propuesta no encontrada.")
    if prop.get("applied"):
        return review  # idempotente

    # Mes siguiente (destino de los cambios).
    nxt_res = await db.execute(
        select(MonthlyPlan)
        .where(MonthlyPlan.annual_plan_id == month.annual_plan_id,
               MonthlyPlan.month_index == month.month_index + 1)
    )
    nxt = nxt_res.scalar_one_or_none()
    if nxt is None:
        raise HTTPException(status_code=409, detail="No hay mes siguiente para aplicar la propuesta.")

    t = prop["type"]
    if t == "carry_over_task":
        carry = await _get_or_create_carryover_objective(nxt.id, db)
        task = (await db.execute(select(ActionTask).where(ActionTask.id == uuid.UUID(prop["task_id"])))).scalar_one_or_none()
        if task is not None:
            task.objective_id = carry.id
    elif t == "new_objective":
        db.add(Objective(monthly_plan_id=nxt.id, title=prop["title"],
                         description=prop.get("description"), kpi_refs=prop.get("kpi_refs", [])))
    elif t == "new_task":
        db.add(ActionTask(objective_id=uuid.UUID(prop["objective_id"]), title=prop["title"],
                          status="pendiente", priority=prop.get("priority", "media"),
                          owner=prop.get("owner"), kpi_ref=prop.get("kpi_ref"), tags=[], order_index=0))

    prop["applied"] = True
    month.review = review
    flag_modified(month, "review")
    await db.flush()
    await db.commit()
    return review


async def _get_or_create_carryover_objective(monthly_plan_id: uuid.UUID, db: AsyncSession) -> Objective:
    res = await db.execute(
        select(Objective).where(
            Objective.monthly_plan_id == monthly_plan_id,
            Objective.title == "Tareas arrastradas",
        )
    )
    obj = res.scalar_one_or_none()
    if obj is None:
        obj = Objective(monthly_plan_id=monthly_plan_id, title="Tareas arrastradas",
                        kpi_refs=[], order_index=99)
        db.add(obj)
        await db.flush()
    return obj
```

- [ ] **Step 4: Correr (pasa)**

Run: `venv/bin/pytest tests/integration/test_month_close_api.py -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Suite backend completa (no romper nada)**

Run: `venv/bin/pytest -q`
Expected: solo la falla preexistente conocida (si aplica en esta rama) — el resto verde. La rama base ya tenía 259/260 verdes; los nuevos tests suman.

- [ ] **Step 6: Commit**

```bash
git add backend/app/api/v1/annual_plan/router.py backend/tests/integration/test_month_close_api.py
git commit -m "feat(review): endpoints close-month y apply-proposal"
```

---

## Task 6: Frontend — capa de datos

**Files:**
- Modify: `frontend/src/lib/annualPlan.ts`

- [ ] **Step 1: Agregar tipos y funciones al final de `frontend/src/lib/annualPlan.ts`**:

```typescript
export type Grade = "bien" | "mal" | "muy_mal"

export interface ReviewSignals {
  tasks_total: number
  tasks_completed: number
  tasks_overdue: number
  completion_pct: number
  kpis: { label: string; value: number | null; target: number | null; unit: string | null; on_track: boolean | null }[]
}

export interface Proposal {
  id: string
  type: "carry_over_task" | "new_objective" | "new_task"
  applied: boolean
  reason?: string
  task_id?: string
  title?: string
  description?: string | null
  kpi_refs?: string[]
  objective_id?: string
  owner?: string | null
  priority?: TaskPriority
  kpi_ref?: string | null
}

export interface MonthReview {
  grade: Grade
  closed_at?: string
  summary: string
  by_agent: Record<string, string>
  signals: ReviewSignals
  proposals: Proposal[]
}

export async function closeMonth(monthIndex: number, kpis: Record<string, number>) {
  const r = await api.post<{ month_index: number; active_month_index: number; grade: Grade }>(
    `/annual-plan/months/${monthIndex}/close`, { kpis },
  )
  return r.data
}

export async function applyProposal(monthIndex: number, proposalId: string): Promise<MonthReview> {
  const r = await api.post<MonthReview>(
    `/annual-plan/months/${monthIndex}/apply-proposal`, { proposal_id: proposalId },
  )
  return r.data
}
```

- [ ] **Step 2: Typecheck**

Run (desde `frontend/`): `npx tsc --noEmit`
Expected: exit 0.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/lib/annualPlan.ts
git commit -m "feat(review-fe): tipos y funciones API de cierre/revisión"
```

---

## Task 7: Frontend — CloseMonthModal + MonthReviewPanel

**Files:**
- Create: `frontend/src/components/plan/CloseMonthModal.tsx`
- Create: `frontend/src/components/plan/MonthReviewPanel.tsx`

- [ ] **Step 1: Crear `frontend/src/components/plan/CloseMonthModal.tsx`**:

```tsx
"use client"

import { useState } from "react"
import { motion } from "framer-motion"
import { X, Loader2 } from "lucide-react"
import AgentsCollaboration from "@/components/plan/AgentsCollaboration"
import type { MonthlyPlan } from "@/lib/annualPlan"

export default function CloseMonthModal({
  month, running, onClose, onSubmit,
}: {
  month: MonthlyPlan
  running: boolean
  onClose: () => void
  onSubmit: (kpis: Record<string, number>) => void
}) {
  const kpiLabels = Array.from(new Set(month.objectives.flatMap(o => o.kpi_refs)))
  const [values, setValues] = useState<Record<string, string>>({})

  const submit = () => {
    const kpis: Record<string, number> = {}
    for (const [k, v] of Object.entries(values)) {
      const n = parseFloat(v)
      if (!Number.isNaN(n)) kpis[k] = n
    }
    onSubmit(kpis)
  }

  return (
    <>
      <motion.div
        initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
        className="fixed inset-0 z-50 bg-black/30 backdrop-blur-sm" onClick={running ? undefined : onClose}
      />
      <motion.div
        initial={{ opacity: 0, scale: 0.97 }} animate={{ opacity: 1, scale: 1 }}
        className="fixed z-50 inset-0 m-auto h-fit max-h-[85vh] w-full max-w-lg overflow-y-auto rounded-2xl bg-white shadow-2xl"
      >
        {running ? (
          <div className="p-10 flex flex-col items-center gap-8">
            <p className="text-sm font-medium text-black">El consejo está revisando tu mes…</p>
            <AgentsCollaboration caption="Los agentes evalúan tu avance y el Challenger cuestiona el resultado antes de darte el veredicto." />
          </div>
        ) : (
          <div className="p-6 space-y-5">
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-bold text-black">Cerrar mes y revisar</h2>
              <button onClick={onClose} className="text-gray-400 hover:text-[var(--gob-navy)]"><X className="h-4 w-4" /></button>
            </div>
            <p className="text-sm text-gray-500 leading-relaxed">
              Ingresa los valores actuales de tus KPIs. El consejo calificará el mes y propondrá ajustes al siguiente.
            </p>
            {kpiLabels.length === 0 ? (
              <p className="text-sm text-gray-400 italic">Este mes no tiene KPIs asociados; el consejo evaluará por el avance de tareas.</p>
            ) : (
              <div className="space-y-3">
                {kpiLabels.map(label => (
                  <div key={label} className="space-y-1">
                    <label className="text-xs font-medium text-gray-600">{label}</label>
                    <input
                      type="number" inputMode="decimal"
                      value={values[label] ?? ""}
                      onChange={e => setValues(v => ({ ...v, [label]: e.target.value }))}
                      placeholder="Valor actual"
                      className="w-full text-sm text-black bg-gray-50 rounded-xl px-3 py-2.5 focus:outline-none focus:bg-white focus:ring-1 focus:ring-[var(--gob-navy)]"
                    />
                  </div>
                ))}
              </div>
            )}
            <button
              onClick={submit}
              className="w-full flex items-center justify-center gap-2 bg-[var(--gob-navy)] text-[var(--gob-bone)] text-sm font-medium px-6 py-3 rounded-xl hover:bg-[var(--gob-ink)] transition-colors"
            >
              <Loader2 className="h-4 w-4 hidden" /> Cerrar mes y pedir revisión
            </button>
          </div>
        )}
      </motion.div>
    </>
  )
}
```

- [ ] **Step 2: Crear `frontend/src/components/plan/MonthReviewPanel.tsx`**:

```tsx
"use client"

import type { MonthReview, Proposal, Grade } from "@/lib/annualPlan"
import { Check, ArrowRight } from "lucide-react"

const GRADE_STYLE: Record<Grade, { label: string; cls: string }> = {
  bien:    { label: "Vas bien",     cls: "bg-emerald-50 text-emerald-700 border-emerald-200" },
  mal:     { label: "Vas mal",      cls: "bg-amber-50 text-amber-700 border-amber-200" },
  muy_mal: { label: "Vas muy mal",  cls: "bg-red-50 text-red-700 border-red-200" },
}

const PROPOSAL_LABEL: Record<Proposal["type"], string> = {
  carry_over_task: "Arrastrar tarea pendiente",
  new_objective:   "Nuevo objetivo",
  new_task:        "Nueva tarea",
}

export default function MonthReviewPanel({
  review, onApply,
}: {
  review: MonthReview
  onApply: (proposalId: string) => void
}) {
  const g = GRADE_STYLE[review.grade]
  return (
    <div className="space-y-4">
      <div className={`inline-flex items-center px-3 py-1.5 rounded-lg border text-sm font-bold ${g.cls}`}>
        {g.label}
      </div>
      <p className="text-sm text-gray-600 leading-relaxed">{review.summary}</p>

      <div className="grid grid-cols-3 gap-2 text-center">
        <div className="rounded-xl border border-gray-100 py-2">
          <p className="text-lg font-bold text-black">{review.signals.completion_pct}%</p>
          <p className="text-[10px] text-gray-400">tareas completadas</p>
        </div>
        <div className="rounded-xl border border-gray-100 py-2">
          <p className="text-lg font-bold text-black">{review.signals.tasks_overdue}</p>
          <p className="text-[10px] text-gray-400">atrasadas</p>
        </div>
        <div className="rounded-xl border border-gray-100 py-2">
          <p className="text-lg font-bold text-black">{review.signals.kpis.filter(k => k.on_track).length}/{review.signals.kpis.length}</p>
          <p className="text-[10px] text-gray-400">KPIs en rumbo</p>
        </div>
      </div>

      {review.proposals.length > 0 && (
        <div className="space-y-2">
          <p className="text-xs font-medium tracking-widest text-gray-400 uppercase">Propuestas para el mes siguiente</p>
          {review.proposals.map(p => (
            <div key={p.id} className="flex items-center gap-3 border border-gray-100 rounded-xl px-3 py-2.5">
              <div className="flex-1">
                <p className="text-sm text-black">
                  <span className="font-medium">{PROPOSAL_LABEL[p.type]}</span>
                  {p.title ? `: ${p.title}` : ""}
                </p>
                {p.reason && <p className="text-[11px] text-gray-400 mt-0.5">{p.reason}</p>}
              </div>
              <button
                onClick={() => onApply(p.id)}
                disabled={p.applied}
                className={`flex items-center gap-1 text-xs font-medium px-2.5 py-1.5 rounded-lg border transition-colors ${
                  p.applied
                    ? "border-emerald-200 bg-emerald-50 text-emerald-600 cursor-default"
                    : "border-gray-200 text-gray-600 hover:border-[var(--gob-navy)] hover:text-[var(--gob-navy)]"
                }`}
              >
                {p.applied ? <><Check className="h-3 w-3" /> Aplicada</> : <><ArrowRight className="h-3 w-3" /> Aplicar</>}
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 3: Typecheck**

Run: `npx tsc --noEmit`
Expected: exit 0.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/plan/CloseMonthModal.tsx frontend/src/components/plan/MonthReviewPanel.tsx
git commit -m "feat(review-fe): CloseMonthModal y MonthReviewPanel"
```

---

## Task 8: Frontend — integración en la página del plan

**Files:**
- Modify: `frontend/src/components/plan/MonthDetail.tsx`
- Modify: `frontend/src/components/plan/MonthTimeline.tsx`
- Modify: `frontend/src/app/dashboard/plan/page.tsx`

- [ ] **Step 1: `MonthDetail.tsx` — botón de cierre (mes activo) + panel de review (mes cerrado)**

Agrega imports al inicio:
```tsx
import { CheckCircle2 } from "lucide-react"
import MonthReviewPanel from "./MonthReviewPanel"
import type { MonthReview } from "@/lib/annualPlan"
```
Extiende las props de `MonthDetail` (agrega dos):
```tsx
  onCloseMonth: (monthlyPlanId: string) => void
  onApplyProposal: (monthIndex: number, proposalId: string) => void
```
Dentro del `return`, JUSTO debajo del bloque del encabezado (`<div> … {month.focus} </div>`), inserta:
```tsx
      {month.status === "done" && month.review && (
        <MonthReviewPanel
          review={month.review as unknown as MonthReview}
          onApply={pid => onApplyProposal(month.month_index, pid)}
        />
      )}
```
Y al final, ANTES del botón "Agregar objetivo", inserta el botón de cierre solo si el mes está activo:
```tsx
      {month.status === "active" && (
        <button
          onClick={() => onCloseMonth(month.id)}
          className="w-full flex items-center justify-center gap-2 bg-[var(--gob-navy)] text-[var(--gob-bone)] text-sm font-medium rounded-xl py-3 hover:bg-[var(--gob-ink)] transition-colors"
        >
          <CheckCircle2 className="h-4 w-4" /> Cerrar mes y revisar
        </button>
      )}
```

- [ ] **Step 2: `MonthTimeline.tsx` — indicador de calificación en meses cerrados**

Dentro del `<button>` de cada mes, donde está el bloque `{isDone && !isSelected && (<span>✓</span>)}`, reemplázalo por un indicador de color según `m.review?.grade`:
```tsx
              {isDone && !isSelected && (() => {
                const grade = (m.review as { grade?: string } | null)?.grade
                const dot = grade === "bien" ? "bg-emerald-500"
                  : grade === "mal" ? "bg-amber-500"
                  : grade === "muy_mal" ? "bg-red-500" : "bg-gray-300"
                return <span className={`h-1.5 w-1.5 rounded-full ${dot}`} />
              })()}
```

- [ ] **Step 3: `page.tsx` — estado del modal + handlers**

Agrega imports:
```tsx
import CloseMonthModal from "@/components/plan/CloseMonthModal"
import { closeMonth, applyProposal } from "@/lib/annualPlan"
```
Agrega estado (junto a los otros `useState`):
```tsx
  const [closingMonthId, setClosingMonthId] = useState<string | null>(null)
  const [closeRunning, setCloseRunning] = useState(false)
```
Agrega handlers (junto a los otros `on*`):
```tsx
  const onCloseMonth = (monthlyPlanId: string) => setClosingMonthId(monthlyPlanId)

  const onSubmitClose = async (kpis: Record<string, number>) => {
    const m = plan?.months.find(mm => mm.id === closingMonthId)
    if (!m) return
    setCloseRunning(true)
    try {
      const res = await closeMonth(m.month_index, kpis)
      await loadPlan()
      setSelectedMonth(res.active_month_index)
    } catch {
      loadPlan().catch(() => setView("error"))
    } finally {
      setCloseRunning(false)
      setClosingMonthId(null)
    }
  }

  const onApplyProposal = async (monthIndex: number, proposalId: string) => {
    try {
      await applyProposal(monthIndex, proposalId)
      await loadPlan()
    } catch {
      loadPlan().catch(() => setView("error"))
    }
  }
```
Pasa las dos props nuevas al `<MonthDetail ...>`:
```tsx
              onCloseMonth={onCloseMonth}
              onApplyProposal={onApplyProposal}
```
Y antes del cierre del componente (junto al `{openTask && <TaskDrawer .../>}`), agrega el modal:
```tsx
      {closingMonthId && (() => {
        const m = plan?.months.find(mm => mm.id === closingMonthId)
        return m ? (
          <CloseMonthModal
            month={m}
            running={closeRunning}
            onClose={() => setClosingMonthId(null)}
            onSubmit={onSubmitClose}
          />
        ) : null
      })()}
```

- [ ] **Step 4: Typecheck + lint de archivos tocados**

Run: `npx tsc --noEmit`
Expected: exit 0.
Run: `npx eslint "src/app/dashboard/plan/page.tsx" "src/components/plan/MonthDetail.tsx" "src/components/plan/MonthTimeline.tsx" "src/components/plan/CloseMonthModal.tsx" "src/components/plan/MonthReviewPanel.tsx"`
Expected: limpio.

- [ ] **Step 5: Build de integración**

Run: `npm run build`
Expected: build exitoso.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/plan/MonthDetail.tsx frontend/src/components/plan/MonthTimeline.tsx frontend/src/app/dashboard/plan/page.tsx
git commit -m "feat(review-fe): integrar cierre de mes y panel de revisión en /dashboard/plan"
```

---

## Task 9: Verificación local (manual)

**Files:** ninguno. El controlador lo coordina con el usuario.

- [ ] **Step 1:** `cd backend && venv/bin/pytest -q` → verde (salvo la falla preexistente conocida si aplica).
- [ ] **Step 2:** `cd frontend && npm run build` → exitoso.
- [ ] **Step 3:** Con el plan sembrado y los servidores arriba, en `/dashboard/plan`:
  - En el mes activo, pulsar **"Cerrar mes y revisar"** → modal de KPIs → enviar → ver la animación → aparece la **calificación** + resumen + propuestas.
  - **Aplicar** una propuesta → confirmar que el cambio aparece en el mes siguiente.
  - El mes cerrado queda con su **calificación** (punto de color en la tira) y muestra el panel de review.
  - Cerrar un mes ya cerrado no debe ofrecerse (el botón solo sale en el activo).

---

## Cierre
- [ ] Suite backend verde + build frontend OK + verificación manual.
- [ ] Pendiente (usuario): decidir merge/push de esta rama y de las apiladas debajo.

## Fuera de alcance (otros subproyectos)
- Cron de cierre automático (D/infra), entregables-archivo por tarea (C), reabrir meses, re-planeo de todos los meses, Secretario (B), gamificación (F).
