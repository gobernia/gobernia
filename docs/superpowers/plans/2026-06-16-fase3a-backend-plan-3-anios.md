# Fase 3A (Backend) — Plan estratégico a 3 años — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Backend del plan estratégico de N años (1/2/3, default 3): columnas nuevas, generador reescrito trimestre-primero con hitos + tareas profesionales (con `required_doc`), orquestación para N×12 meses, y API que acepta el horizonte — todo testeable con pytest.

**Architecture:** Reutiliza `AnnualPlan→MonthlyPlan→Objective→ActionTask`. El generador produce: (1) **hitos** del horizonte (`plan.milestones` JSONB), (2) por cada trimestre, una llamada que devuelve los **3 meses** del trimestre con objetivos + tareas medibles (con `required_doc`). La task de Celery crea N×12 meses. Se generaliza el tope 1..12 a 1..N×12.

**Tech Stack:** FastAPI, SQLAlchemy async, Celery (`task_session`), anthropic SDK (`_create_with_retry`/`_extract_json_object`, `settings.AI_MODEL`). Columnas nuevas vía script ALTER idempotente (NO Alembic — ver memoria `prod-schema-no-alembic`).

**Verificación:** pytest (`cd backend && ./venv/bin/pytest`). Lógica pura (parsers, calendario) sin red; orquestación/endpoint mockean la IA. La columna en prod (`scripts/alter_plan_3anios.py`) se corre en integración/deploy con autorización.

---

### Task 1: Columnas nuevas (horizon_years, milestones, required_doc) + script ALTER

**Files:**
- Modify: `backend/app/models/annual_plan.py`, `backend/app/models/action_plan.py`
- Create: `backend/scripts/alter_plan_3anios.py`
- Test: `backend/tests/unit/test_plan_3anios_columns.py` (crear)

- [ ] **Step 1: Test de que los modelos tienen las columnas nuevas**

`backend/tests/unit/test_plan_3anios_columns.py`:

```python
from app.models.annual_plan import AnnualPlan
from app.models.action_plan import ActionTask


def test_annual_plan_tiene_horizon_y_milestones():
    cols = AnnualPlan.__table__.columns.keys()
    assert "horizon_years" in cols
    assert "milestones" in cols


def test_action_task_tiene_required_doc():
    assert "required_doc" in ActionTask.__table__.columns.keys()


def test_horizon_default_3():
    # el default de la columna es 3
    assert AnnualPlan.__table__.columns["horizon_years"].default.arg == 3
```

- [ ] **Step 2: Correr (falla)**

Run: `cd backend && ./venv/bin/pytest tests/unit/test_plan_3anios_columns.py -q`
Expected: FAIL.

- [ ] **Step 3: Agregar columnas a `AnnualPlan`**

En `backend/app/models/annual_plan.py`, dentro de `class AnnualPlan`, junto a los demás campos (importar `Integer` y `JSONB` si no están — `JSONB` ya se importa para MonthlyPlan):

```python
    horizon_years: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    milestones: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
```

- [ ] **Step 4: Agregar columna a `ActionTask`**

En `backend/app/models/action_plan.py`, dentro de `class ActionTask`, junto a los demás campos:

```python
    required_doc: Mapped[str | None] = mapped_column(Text, nullable=True)
```

(`Text` ya está importado en ese archivo — verificar; si no, agregarlo a los imports de sqlalchemy.)

- [ ] **Step 5: Script ALTER idempotente**

`backend/scripts/alter_plan_3anios.py` (espejo de `scripts/create_annual_plan_tables.py`):

```python
"""Agrega columnas para el plan a N años SIN Alembic (prod usa create_all + ALTER).
Idempotente: ADD COLUMN IF NOT EXISTS.
USO (solo cuando el humano lo autorice — toca la DB):
    venv/bin/python -m scripts.alter_plan_3anios
"""
import asyncio

from sqlalchemy import text

from app.db.session import engine
import app.models  # noqa: F401
from app.models import Base


async def main():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.execute(text(
            "ALTER TABLE annual_plans ADD COLUMN IF NOT EXISTS horizon_years INTEGER NOT NULL DEFAULT 3"))
        await conn.execute(text(
            "ALTER TABLE annual_plans ADD COLUMN IF NOT EXISTS milestones JSONB"))
        await conn.execute(text(
            "ALTER TABLE action_tasks ADD COLUMN IF NOT EXISTS required_doc TEXT"))
    await engine.dispose()
    print("OK: columnas del plan a 3 años agregadas")


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 6: Correr (pasa) + suite completa**

Run: `cd backend && ./venv/bin/pytest tests/unit/test_plan_3anios_columns.py -q && ./venv/bin/pytest -q`
Expected: nuevo test verde; suite completa verde (las columnas nuevas son opcionales, no rompen serialización existente).

- [ ] **Step 7: Commit**

```bash
git add backend/app/models/annual_plan.py backend/app/models/action_plan.py backend/scripts/alter_plan_3anios.py backend/tests/unit/test_plan_3anios_columns.py
git commit -m "feat(fase3a): columnas horizon_years/milestones/required_doc + script ALTER"
```

---

### Task 2: Generalizar el indexado 1..12 → 1..N×12

**Files:**
- Modify: `backend/app/services/ai/annual_plan_generator.py` (`compute_active_month_index`)
- Modify: `backend/app/api/v1/annual_plan/router.py` (`_run_close` tope `< 12`)
- Test: `backend/tests/unit/test_active_month_index.py` (crear)

- [ ] **Step 1: Test del cap parametrizable**

`backend/tests/unit/test_active_month_index.py`:

```python
from datetime import date
from app.services.ai.annual_plan_generator import compute_active_month_index


def test_cap_default_12():
    # 5 años después → sin total_months, sigue capeando en 12 (compat)
    assert compute_active_month_index(date(2020, 1, 1), date(2030, 1, 1)) == 12


def test_cap_a_total_months():
    # plan de 3 años (36 meses): a los 20 meses, índice 21; capea en 36
    start = date(2026, 1, 1)
    assert compute_active_month_index(start, date(2027, 9, 1), total_months=36) == 21
    assert compute_active_month_index(start, date(2031, 1, 1), total_months=36) == 36


def test_minimo_1():
    assert compute_active_month_index(date(2026, 6, 1), date(2026, 1, 1), total_months=36) == 1
```

- [ ] **Step 2: Correr (falla)** — `total_months` no existe aún.

Run: `cd backend && ./venv/bin/pytest tests/unit/test_active_month_index.py -q`

- [ ] **Step 3: Parametrizar `compute_active_month_index`**

En `annual_plan_generator.py`, cambiar la firma y el cap (hoy: `return min(max(elapsed + 1, 1), 12)`):

```python
def compute_active_month_index(start_date: date, today: date, total_months: int = 12) -> int:
    """Índice (1..total_months) del mes vigente del plan según hoy. Cap en [1, total_months]."""
    elapsed = (today.year - start_date.year) * 12 + (today.month - start_date.month)
    return min(max(elapsed + 1, 1), total_months)
```

- [ ] **Step 4: Generalizar el tope en `_run_close`**

En `router.py` (~línea 462), hoy: `active_idx = month_index + 1 if month_index < 12 else month_index`. Cambiar el `12` por el total de meses del plan. El total = `plan.horizon_years * 12` (cargar el plan ya disponible en esa función). Concretamente:

```python
    total_months = (plan.horizon_years or 1) * 12
    active_idx = month_index + 1 if month_index < total_months else month_index
```

(Leer el contexto de `_run_close` para usar la variable `plan` correcta; si ahí no está el `plan`, usar el `annual_plan` que esa función ya carga.)

- [ ] **Step 5: Correr (pasa) + suite**

Run: `cd backend && ./venv/bin/pytest tests/unit/test_active_month_index.py -q && ./venv/bin/pytest -q`
Expected: verde. Los llamados existentes a `compute_active_month_index(start, today)` siguen funcionando (default 12).

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/ai/annual_plan_generator.py backend/app/api/v1/annual_plan/router.py backend/tests/unit/test_active_month_index.py
git commit -m "feat(fase3a): compute_active_month_index parametrizable + cierre de mes a N meses"
```

---

### Task 3: Generador de hitos (milestones)

**Files:**
- Modify: `backend/app/services/ai/annual_plan_generator.py`
- Test: `backend/tests/unit/test_milestones_generator.py` (crear)

- [ ] **Step 1: Tests de la lógica pura (`parse_milestones`)**

`backend/tests/unit/test_milestones_generator.py`:

```python
import json
from app.services.ai.annual_plan_generator import parse_milestones, _milestones_vacio


def test_parse_milestones_ok():
    payload = {"milestones": [
        {"type": "trimestral", "year": 1, "period": 1, "title": "Q1", "target": "11% margen", "kpi_ref": "Margen"},
        {"type": "anual", "year": 1, "period": 1, "title": "Año 1", "target": "crecer 20%", "kpi_ref": None},
    ]}
    out = parse_milestones(json.dumps(payload))
    assert out["items"][0]["type"] == "trimestral"
    assert out["items"][0]["target"] == "11% margen"
    assert out["items"][1]["kpi_ref"] is None
    assert not _milestones_vacio(out)


def test_parse_milestones_descarta_tipo_invalido():
    payload = {"milestones": [{"type": "raro", "year": 1, "period": 1, "title": "x", "target": "y"}]}
    out = parse_milestones(json.dumps(payload))
    assert out["items"] == []
    assert _milestones_vacio(out)


def test_parse_basura():
    out = parse_milestones("no json")
    assert _milestones_vacio(out)
```

- [ ] **Step 2: Correr (falla)**

Run: `cd backend && ./venv/bin/pytest tests/unit/test_milestones_generator.py -q`

- [ ] **Step 3: Implementar parser + generador de hitos**

Agregar a `annual_plan_generator.py`:

```python
_MILESTONE_TYPES = {"trimestral", "semestral", "anual"}

MILESTONES_SYSTEM_PROMPT = """Eres el director estratégico del consejo de Gobernia.
A partir del diagnóstico, la visión y los KPIs, diseñas los HITOS de un plan estratégico
de varios años. Para un horizonte de N años generas:
- un hito TRIMESTRAL por cada trimestre (N×4),
- un hito SEMESTRAL por cada semestre (N×2),
- un hito ANUAL por cada año (N).
Cada hito tiene "title" (corto) y "target" = META MEDIBLE (ej. "alcanzar 11% de margen
después de impuestos"), atada a un KPI de la lista cuando aplique ("kpi_ref", o null).
Progresión lógica: lo trimestral aporta a lo semestral, y eso a lo anual.
Usa SOLO labels de la lista de KPIs provista."""

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
        f"VISIÓN A 3 AÑOS: {(memory_buffer.get('vision') or {}).get('three_year_view', 'N/D')}\n\n"
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
```

> Nota: `_company_line`, `settings`, `anthropic`, `_create_with_retry`, `_extract_json_object` ya existen/están importados en el archivo. Confirmar la clave real de la visión en `memory_buffer` (la Etapa 8 guarda `three_year_view`); si la ruta difiere, ajustar el `.get(...)` leyendo `app/services/ai/memory_buffer.py`.

- [ ] **Step 4: Correr (pasa)**

Run: `cd backend && ./venv/bin/pytest tests/unit/test_milestones_generator.py -q`

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/ai/annual_plan_generator.py backend/tests/unit/test_milestones_generator.py
git commit -m "feat(fase3a): generador de hitos (milestones) + parser"
```

---

### Task 4: Generador por trimestre (3 meses con objetivos + tareas profesionales)

**Files:**
- Modify: `backend/app/services/ai/annual_plan_generator.py`
- Test: `backend/tests/unit/test_quarter_generator.py` (crear)

`generate_quarter_plan` devuelve los **3 meses** del trimestre, cada uno con `month_index` global, `focus`, y `objectives` (cada uno con `tasks`). Las tareas son medibles y pueden traer `required_doc`.

- [ ] **Step 1: Tests de `parse_quarter_plan` y `quarter_month_indices`**

`backend/tests/unit/test_quarter_generator.py`:

```python
import json
from app.services.ai.annual_plan_generator import parse_quarter_plan, quarter_month_indices


def test_quarter_month_indices():
    # año 1 trimestre 1 → meses globales 1,2,3 ; año 1 trimestre 4 → 10,11,12 ; año 2 trimestre 1 → 13,14,15
    assert quarter_month_indices(1, 1) == [1, 2, 3]
    assert quarter_month_indices(1, 4) == [10, 11, 12]
    assert quarter_month_indices(2, 1) == [13, 14, 15]


def test_parse_quarter_ok():
    payload = {"months": [
        {"month_in_quarter": 1, "focus": "F1", "objectives": [
            {"title": "Obj", "description": "d", "kpi_refs": ["Margen"], "tasks": [
                {"title": "Subir margen", "owner": "CFO", "priority": "alta",
                 "kpi_ref": "Margen", "required_doc": "estado de resultados", "due_day": 15}
            ]}
        ]},
        {"month_in_quarter": 2, "focus": "F2", "objectives": []},
        {"month_in_quarter": 3, "focus": "F3", "objectives": []},
    ]}
    months = parse_quarter_plan(json.dumps(payload), year=1, quarter=1)
    assert [m["month_index"] for m in months] == [1, 2, 3]
    t = months[0]["objectives"][0]["tasks"][0]
    assert t["required_doc"] == "estado de resultados"
    assert t["priority"] == "alta"
    assert t["owner"] == "CFO"


def test_parse_quarter_basura_da_3_meses_vacios():
    months = parse_quarter_plan("no json", year=1, quarter=2)
    assert [m["month_index"] for m in months] == [4, 5, 6]
    assert all(m["objectives"] == [] for m in months)
```

- [ ] **Step 2: Correr (falla)**

Run: `cd backend && ./venv/bin/pytest tests/unit/test_quarter_generator.py -q`

- [ ] **Step 3: Implementar**

Agregar a `annual_plan_generator.py` (reusa `_norm_priority`, `_norm_tags`, `due_date_within_month`, `month_calendar`, `_company_line`):

```python
def quarter_month_indices(year: int, quarter: int) -> list[int]:
    """Índices de mes GLOBALES (1-based) de los 3 meses de un (año, trimestre)."""
    base = (year - 1) * 12 + (quarter - 1) * 3
    return [base + 1, base + 2, base + 3]


QUARTER_SYSTEM_PROMPT = """Eres el director del consejo. Para UN trimestre del plan estratégico,
diseñas los 3 MESES con objetivos y TAREAS PROFESIONALES Y MEDIBLES (no genéricas).

Reglas de las tareas:
1. "title": acción concreta y MEDIBLE atada a la meta del trimestre/KPI
   (ej. "Subir el margen después de impuestos hacia 11%"), no vaguedades.
2. "owner": rol responsable (CFO, Director Comercial, etc.).
3. "priority": "alta"|"media"|"baja".
4. "kpi_ref": un KPI de la lista que la tarea mueve, o null.
5. "required_doc": el DOCUMENTO/DATO actualizado que SUSTENTA la meta cuando aplica
   (ej. "estado de resultados del mes"), o null si no requiere sustento.
6. "due_day": día del mes (1-28).
Reparte el trabajo en los 3 meses (month_in_quarter 1,2,3). 2-4 tareas por mes. Calidad sobre cantidad."""

QUARTER_SCHEMA = """{
  "months": [
    {"month_in_quarter": 1, "focus": "string", "objectives": [
      {"title": "string", "description": "string", "kpi_refs": ["KPI label"], "tasks": [
        {"title": "string", "owner": "string", "priority": "alta|media|baja",
         "kpi_ref": "KPI label|null", "required_doc": "string|null", "due_day": 15}
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
```

- [ ] **Step 4: Correr (pasa)**

Run: `cd backend && ./venv/bin/pytest tests/unit/test_quarter_generator.py -q`

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/ai/annual_plan_generator.py backend/tests/unit/test_quarter_generator.py
git commit -m "feat(fase3a): generador por trimestre (3 meses, objetivos+tareas medibles+required_doc)"
```

---

### Task 5: Reescribir la orquestación (`_run_generation`)

**Files:**
- Modify: `backend/app/tasks/annual_plan_tasks.py`
- Test: `backend/tests/unit/test_run_generation_3anios.py` (crear)

El nuevo `_run_generation`: carga onboarding, idempotencia (borra meses previos), diagnóstico (igual que hoy), **genera hitos → los guarda en `plan.milestones`**, calcula `total_months = horizon_years*12` y `active_idx`, **por cada trimestre (N×4) llama `generate_quarter_plan` (paralelizable)** → crea los 3 `MonthlyPlan` con sus `Objective`/`ActionTask` (con `required_doc`), status `active/done/locked` por `month_index` vs `active_idx`, `plan.status="active"`.

- [ ] **Step 1: Test de orquestación (IA mockeada)**

`backend/tests/unit/test_run_generation_3anios.py`: mockea `generate_milestones` y `generate_quarter_plan` (y `run_diagnostico`/`synthesize_diagnostico`) y verifica que para `horizon_years=1` se crean 12 `MonthlyPlan` y `plan.milestones` se setea. Patrón con `AsyncMock`/`MagicMock` + `patch` como en `tests/unit/test_diagnostico_task.py`. Concretamente, mockear las funciones del generador en el namespace de `annual_plan_tasks` y un `db` AsyncMock que capture los `db.add(...)`; asertar el número de `MonthlyPlan` añadidos = 12 y que `plan.milestones` quedó seteado y `plan.status == "active"`.

(El implementador escribe el test mirando el patrón de `test_diagnostico_task.py`; el objetivo es fijar: 12 meses para horizonte 1, hitos persistidos, status active. Si construir el mock del loop de `db.add` resulta frágil, testear en su lugar una función helper pura extraída — ver Step 2 — y dejar la orquestación cubierta por el smoke de integración.)

- [ ] **Step 2: Reescribir `_run_generation` y el helper de trimestres**

Leer el `_run_generation` actual. Reemplazar la fase de esqueleto+meses por:

```python
# tras cargar memory_buffer, hacer idempotencia y diagnóstico (igual que hoy):
from app.services.ai.annual_plan_generator import (
    generate_milestones, generate_quarter_plan, compute_active_month_index,
    month_calendar, due_date_within_month,
)
# `kpi_labels_from_buffer` YA está definido en este mismo módulo (annual_plan_tasks.py:16) — no importarlo.

horizon = plan.horizon_years or 3
total_months = horizon * 12
kpi_labels = kpi_labels_from_buffer(memory_buffer)  # helper local del módulo, el mismo que usa el esqueleto hoy

# Paso 1: hitos
milestones = await asyncio.to_thread(
    generate_milestones, memory_buffer, plan.diagnostico_summary, kpi_labels, horizon)
plan.milestones = milestones

active_idx = compute_active_month_index(plan.start_date, date.today(), total_months)

# Paso 2: por trimestre (paralelo), cada uno devuelve 3 meses
quarters = [(y, q) for y in range(1, horizon + 1) for q in range(1, 5)]
sem = asyncio.Semaphore(_MONTH_CONCURRENCY)
async def _one_quarter(y, q):
    async with sem:
        return await asyncio.to_thread(
            generate_quarter_plan, memory_buffer, kpi_labels, milestones, y, q)
quarter_results = await asyncio.gather(*[_one_quarter(y, q) for (y, q) in quarters])

# Paso 3: persistir N×12 meses
for months in quarter_results:
    for mspec in months:  # cada mspec = {month_index, focus, objectives:[{...,tasks:[...]}]}
        mi = mspec["month_index"]
        year, month = month_calendar(plan.start_date.year, plan.start_date.month, mi)
        status = "active" if mi == active_idx else ("done" if mi < active_idx else "locked")
        mp = MonthlyPlan(annual_plan_id=plan.id, month_index=mi, period_year=year,
                         period_month=month, focus=mspec.get("focus"), status=status)
        db.add(mp); await db.flush()
        for oi, ospec in enumerate(mspec["objectives"]):
            obj = Objective(monthly_plan_id=mp.id, title=ospec["title"],
                            description=ospec.get("description"),
                            kpi_refs=ospec.get("kpi_refs") or [], order_index=oi)
            db.add(obj); await db.flush()
            for ti, tspec in enumerate(ospec.get("tasks") or []):
                db.add(ActionTask(
                    objective_id=obj.id, user_id=plan.user_id,
                    title=tspec["title"], description=tspec.get("description"),
                    owner=tspec.get("owner"), priority=tspec["priority"],
                    kpi_ref=tspec.get("kpi_ref"), required_doc=tspec.get("required_doc"),
                    tags=tspec.get("tags") or [],
                    due_date=due_date_within_month(year, month, int(tspec.get("due_day", 28))),
                    order_index=ti, status="pendiente"))

plan.status = "active"
await db.commit()
```

> El implementador debe **conservar** la parte de diagnóstico/genesis BoardSession y el manejo de excepción (rollback→failed→raise) tal como están hoy; solo se reemplaza la generación de meses. Ajustar nombres reales de helpers (`kpi_labels_from_buffer` o como se llame el que extrae labels del buffer — leer cómo lo hace hoy `_run_generation` al llamar `generate_skeleton`) y los campos exactos del constructor `ActionTask`/`Objective`/`MonthlyPlan` (leer el código actual). El `MonthlyPlan` debe setear `annual_plan_id=plan.id`.

- [ ] **Step 3: Correr el test + suite**

Run: `cd backend && ./venv/bin/pytest tests/unit/test_run_generation_3anios.py -q && ./venv/bin/pytest -q`
Expected: verde. Si el test de orquestación quedó frágil, dejarlo cubriendo lo esencial (12 meses + milestones + status) o reducir a verificar el helper.

- [ ] **Step 4: Commit**

```bash
git add backend/app/tasks/annual_plan_tasks.py backend/tests/unit/test_run_generation_3anios.py
git commit -m "feat(fase3a): orquestación trimestre-primero (N×12 meses + hitos)"
```

---

### Task 6: API — horizonte en generate + schemas de salida

**Files:**
- Modify: `backend/app/schemas/annual_plan.py`, `backend/app/schemas/action_plan.py`
- Modify: `backend/app/api/v1/annual_plan/router.py`
- Test: `backend/tests/integration/test_generate_horizon.py` (crear)

- [ ] **Step 1: Esquemas de salida + request**

En `app/schemas/annual_plan.py`:
- `AnnualPlanOut`: agregar `horizon_years: int = 3` y `milestones: dict | None = None`.
- `MonthlyPlanOut`: (sin cambios).
- Nuevo request:
  ```python
  from pydantic import Field
  class GeneratePlanRequest(BaseModel):
      horizon_years: int = Field(default=3, ge=1, le=3)
  ```
En `app/schemas/action_plan.py`, en `ActionTaskOut`: agregar `required_doc: str | None = None`.

- [ ] **Step 2: Endpoint `generate` acepta el horizonte**

En `router.py`, `generate_plan`: agregar el body opcional y persistirlo. Cambiar la firma a:

```python
async def generate_plan(
    body: GeneratePlanRequest = GeneratePlanRequest(),
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
```

Y donde se crea el `AnnualPlan(...)`, pasar `horizon_years=body.horizon_years` y un `title` dinámico (p. ej. `f"Plan estratégico de {body.horizon_years} año(s)"`). (FastAPI: un body con todos los campos con default permite POST sin body — el default aplica.)

- [ ] **Step 3: GET devuelve los campos nuevos**

En `get_plan`, donde construye `AnnualPlanOut(...)`, agregar `horizon_years=plan.horizon_years`, `milestones=plan.milestones`. En `_task_out`, agregar `required_doc=t.required_doc`. (Verificar que el `selectinload`/serialización incluye el campo.)

- [ ] **Step 4: Test de integración**

`backend/tests/integration/test_generate_horizon.py`: patrón de `tests/integration/test_board_themes_api.py`. Verifica: (a) POST `/annual-plan/generate` con `{"horizon_years": 3}` y onboarding completo+KPIs → 200/encola (Celery mockeado con `boom` como en `test_generate_seeds_themes`) y que el plan creado tiene `horizon_years==3`; (b) `horizon_years` fuera de 1-3 → 422.

- [ ] **Step 5: Correr la suite nueva + completa**

Run: `cd backend && ./venv/bin/pytest tests/integration/test_generate_horizon.py -q && ./venv/bin/pytest -q`
Expected: verde.

- [ ] **Step 6: Commit**

```bash
git add backend/app/schemas/annual_plan.py backend/app/schemas/action_plan.py backend/app/api/v1/annual_plan/router.py backend/tests/integration/test_generate_horizon.py
git commit -m "feat(fase3a): API acepta horizon_years; expone milestones + required_doc"
```

---

## Self-Review (cobertura del spec)

- **Componente 1 (modelo: horizon_years/milestones/required_doc + ALTER)** → Task 1. ✅
- **Componente 2 (generador trimestre-primero):** hitos → Task 3; trimestre→3 meses con tareas+required_doc → Task 4; orquestación N×12 → Task 5. Indexado 1..N×12 → Task 2. ✅
- **Componente 3 (API: horizon_years en generate; GET expone milestones+required_doc)** → Task 6. ✅
- **Componente 4 (frontend)** → NO está aquí (plan de frontend aparte). ✅

Consistencia: `parse_quarter_plan` devuelve meses con `month_index` global (de `quarter_month_indices`); la orquestación los usa tal cual. `required_doc` fluye tarea→`ActionTask.required_doc`→`ActionTaskOut`. `milestones` = `{"items":[...]}` consistente entre `generate_milestones`/`plan.milestones`/`AnnualPlanOut`. `horizon_years` default 3 en modelo, request y schema. `compute_active_month_index(start, today, total_months)` retrocompatible (default 12).

Puntos a confirmar en implementación (marcados): nombre real del helper que extrae `kpi_labels` del buffer; clave real de la visión en `memory_buffer` (`three_year_view`); campos exactos de los constructores `MonthlyPlan/Objective/ActionTask`; ubicación de `plan` en `_run_close`. La columna en prod (`scripts/alter_plan_3anios.py`) se corre en integración/deploy con autorización.
