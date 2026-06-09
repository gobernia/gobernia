# Bloque B3b — Tablero de Acuerdos (Monday) · Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Un Tablero de Acuerdos tipo Monday en `/dashboard/plan` (toggle Meses/Tablero): 3 columnas por estado con drag-and-drop, gate al validar sin evidencia, e indicador de evidencia.

**Architecture:** Backend añade `evidence_count` a la salida de tareas del plan (una consulta agrupada en `get_plan`). Frontend: un componente `AcuerdosBoard` que aplana el plan ya cargado en 3 columnas con dnd-kit; mover entre columnas reusa el `onUpdateTask` optimista existente; el gate del front evita soltar en "Validado" sin evidencia.

**Tech Stack:** FastAPI, SQLAlchemy async, Pydantic v2, pytest (asyncio, db mockeada), Next.js 16 + TS, @dnd-kit/core (ya instalado).

**Spec:** `docs/superpowers/specs/2026-06-08-bloque-b3b-tablero-acuerdos-design.md`

**Patrones existentes:**
- `app/api/v1/annual_plan/router.py`: `_task_out(t)`, `_objective_out(o, tasks)`, `get_plan` (reúne tareas con `_tasks_by_objective`; `grouped = {objective_id: [ActionTask]}`). `ActionTaskOut` en `app/schemas/action_plan.py`. `Evidence` en `app/models/evidence.py`.
- Frontend plan page `src/app/dashboard/plan/page.tsx`: estado `plan`, `selectedMonth`, `openTask`/`setOpenTask`; handler `onUpdateTask(taskId, patch)` (optimista: `patchTaskLocal` + `updateTask`). Vista activa (~línea 262) renderiza `MonthTimeline` + `MonthDetail`; `TaskDrawer` se abre con `openTask`. `Task`/`MonthlyPlan`/`AnnualPlan`/`MONTH_NAMES` en `src/lib/annualPlan.ts`.
- DnD de referencia: `src/app/dashboard/sesion/[id]/plan/page.tsx` (dnd-kit, `handleDragEnd` con columnas por status).

---

### Task 1: Backend — `evidence_count` en el plan

**Files:**
- Modify: `backend/app/schemas/action_plan.py` (`ActionTaskOut`)
- Modify: `backend/app/api/v1/annual_plan/router.py` (imports, `_task_out`, `_objective_out`, `get_plan`)
- Test: `backend/tests/integration/test_plan_evidence_count.py`

- [ ] **Step 1: Write the failing test** at `backend/tests/integration/test_plan_evidence_count.py`:

```python
import uuid
from datetime import date, datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.models.action_plan import ActionTask
from app.models.annual_plan import AnnualPlan, MonthlyPlan, Objective
from app.api.v1.annual_plan.router import _task_out, _objective_out
from app.core.dependencies import get_current_user_id, get_db

MOCK_USER_ID = "user_test_evcount"
NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _task(objective_id=None):
    t = ActionTask(id=uuid.uuid4(), plan_id=None, objective_id=objective_id,
                   title="A", status="pendiente", priority="media", order_index=0)
    t.created_at = NOW; t.updated_at = NOW
    t.kpi_ref = None; t.description = None; t.source_agent = None
    t.owner = None; t.due_date = None; t.tags = None
    return t


def test_task_out_threads_evidence_count():
    t = _task()
    assert _task_out(t, 3).evidence_count == 3


def test_task_out_defaults_zero():
    t = _task()
    assert _task_out(t).evidence_count == 0


def test_objective_out_threads_counts():
    obj = Objective(id=uuid.uuid4(), monthly_plan_id=uuid.uuid4(), title="O", order_index=0)
    obj.kpi_refs = None
    t = _task(objective_id=obj.id)
    out = _objective_out(obj, [t], {t.id: 5})
    assert out.tasks[0].evidence_count == 5


def _db_override(db):
    async def override():
        yield db
    return override


async def _user_override():
    return MOCK_USER_ID


@pytest.mark.asyncio
async def test_get_plan_includes_evidence_count():
    plan = AnnualPlan(id=uuid.uuid4(), user_id=MOCK_USER_ID, title="P",
                      start_date=date.today(), status="active")
    plan.diagnostico_summary = None; plan.genesis_session_id = None
    month = MonthlyPlan(id=uuid.uuid4(), annual_plan_id=plan.id, month_index=1,
                        period_year=2026, period_month=1, status="active")
    month.focus = None; month.review = None
    obj = Objective(id=uuid.uuid4(), monthly_plan_id=month.id, title="O", order_index=0)
    obj.kpi_refs = None
    month.objectives = [obj]
    plan.months = [month]
    task = _task(objective_id=obj.id)

    r1 = MagicMock(); r1.scalar_one_or_none.return_value = plan           # plan query
    r2 = MagicMock(); r2.scalars.return_value.all.return_value = [task]   # _tasks_by_objective
    r3 = MagicMock(); r3.all.return_value = [(task.id, 2)]                # evidence count
    db = AsyncMock(); db.execute = AsyncMock(side_effect=[r1, r2, r3])

    app.dependency_overrides[get_db] = _db_override(db)
    app.dependency_overrides[get_current_user_id] = _user_override
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.get("/api/v1/annual-plan")
    finally:
        app.dependency_overrides.clear()

    assert r.status_code == 200
    body = r.json()
    assert body["months"][0]["objectives"][0]["tasks"][0]["evidence_count"] == 2
```

- [ ] **Step 2: Run it, verify it FAILS** (`evidence_count` no existe en ActionTaskOut / `_task_out` no acepta el arg):
`cd backend && venv/bin/python -m pytest tests/integration/test_plan_evidence_count.py -v`

- [ ] **Step 3: Add `evidence_count` to `ActionTaskOut`.** In `backend/app/schemas/action_plan.py`, add to the `ActionTaskOut` class (after `updated_at`):
```python
    evidence_count: int = 0
```

- [ ] **Step 4: Thread it through the serializers.** In `backend/app/api/v1/annual_plan/router.py`:

Add imports — ensure `func` is imported from sqlalchemy (change `from sqlalchemy import select` to `from sqlalchemy import func, select`) and add `from app.models.evidence import Evidence`.

Change `_task_out` to accept the count:
```python
def _task_out(t: ActionTask, evidence_count: int = 0) -> ActionTaskOut:
    return ActionTaskOut(
        id=str(t.id),
        plan_id=str(t.plan_id) if t.plan_id else None,
        objective_id=str(t.objective_id) if t.objective_id else None,
        kpi_ref=t.kpi_ref,
        title=t.title, description=t.description, source_agent=t.source_agent,
        status=t.status, priority=t.priority, owner=t.owner, due_date=t.due_date,
        tags=list(t.tags or []), order_index=t.order_index,
        created_at=t.created_at, updated_at=t.updated_at,
        evidence_count=evidence_count,
    )
```

Change `_objective_out` to accept and pass the counts:
```python
def _objective_out(o: Objective, tasks: list[ActionTask], evidence_counts: dict | None = None) -> ObjectiveOut:
    counts = evidence_counts or {}
    return ObjectiveOut(
        id=str(o.id), title=o.title, description=o.description,
        kpi_refs=list(o.kpi_refs or []), order_index=o.order_index,
        tasks=[_task_out(t, counts.get(t.id, 0)) for t in tasks],
    )
```

- [ ] **Step 5: Compute the counts in `get_plan`.** After `grouped = await _tasks_by_objective(all_obj_ids, db)` and before building `months_out`, add:
```python
    task_ids = [t.id for tasks in grouped.values() for t in tasks]
    evidence_counts: dict = {}
    if task_ids:
        cres = await db.execute(
            select(Evidence.action_task_id, func.count())
            .where(Evidence.action_task_id.in_(task_ids))
            .group_by(Evidence.action_task_id)
        )
        evidence_counts = {tid: cnt for tid, cnt in cres.all()}
```
Then pass the map in the months build — change `_objective_out(o, grouped.get(o.id, []))` to:
```python
            objectives=[_objective_out(o, grouped.get(o.id, []), evidence_counts) for o in m.objectives],
```

- [ ] **Step 6: Run the test, verify it PASSES** (4 passed):
`cd backend && venv/bin/python -m pytest tests/integration/test_plan_evidence_count.py -v`

- [ ] **Step 7: Run the full backend suite (no regressions):**
`cd backend && venv/bin/python -m pytest -q`

- [ ] **Step 8: Commit:**
```bash
git add backend/app/schemas/action_plan.py backend/app/api/v1/annual_plan/router.py backend/tests/integration/test_plan_evidence_count.py
git commit -m "feat(b3b): evidence_count por tarea en GET /annual-plan"
```

---

### Task 2: Frontend — Tablero de Acuerdos

**Files:**
- Modify: `frontend/src/lib/annualPlan.ts` (campo `evidence_count` en `Task`)
- Create: `frontend/src/components/plan/AcuerdosBoard.tsx`
- Modify: `frontend/src/app/dashboard/plan/page.tsx` (toggle + render del board)

- [ ] **Step 1: Add `evidence_count` to the `Task` type.** In `frontend/src/lib/annualPlan.ts`, add to the `Task` interface (after `updated_at`):
```typescript
  evidence_count: number
```

- [ ] **Step 2: Create the board** `frontend/src/components/plan/AcuerdosBoard.tsx`:

```tsx
"use client"

import { useState } from "react"
import {
  DndContext, PointerSensor, useSensor, useSensors,
  useDraggable, useDroppable, type DragEndEvent,
} from "@dnd-kit/core"
import { Paperclip } from "lucide-react"
import { AnnualPlan, MonthlyPlan, Task, MONTH_NAMES } from "@/lib/annualPlan"

const COLUMNS: { id: Task["status"]; label: string }[] = [
  { id: "pendiente", label: "Pendiente" },
  { id: "en_progreso", label: "En proceso" },
  { id: "completada", label: "Validado" },
]
const PRIO_DOT: Record<string, string> = { alta: "bg-red-400", media: "bg-amber-400", baja: "bg-gray-300" }

type Item = { task: Task; month: MonthlyPlan }

function Card({ item, onClick }: { item: Item; onClick: () => void }) {
  const { attributes, listeners, setNodeRef, transform, isDragging } = useDraggable({ id: item.task.id })
  const style = transform
    ? { transform: `translate(${transform.x}px, ${transform.y}px)`, zIndex: 50 }
    : undefined
  const t = item.task
  return (
    <div
      ref={setNodeRef} style={style} {...attributes} {...listeners}
      onClick={onClick}
      className={`bg-white border border-gray-100 rounded-xl p-3 space-y-2 cursor-grab active:cursor-grabbing ${isDragging ? "opacity-50" : ""}`}
    >
      <p className="text-sm text-black font-medium leading-snug">{t.title}</p>
      <div className="flex items-center gap-2 text-[11px] text-gray-400">
        <span className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${PRIO_DOT[t.priority] ?? "bg-gray-300"}`} />
        <span>{MONTH_NAMES[item.month.period_month]}</span>
        {t.owner && <span className="truncate">· {t.owner}</span>}
        {t.evidence_count > 0 && (
          <span className="ml-auto inline-flex items-center gap-0.5 text-gray-500">
            <Paperclip className="h-3 w-3" />{t.evidence_count}
          </span>
        )}
      </div>
    </div>
  )
}

function Column({
  id, label, items, onTaskClick,
}: { id: Task["status"]; label: string; items: Item[]; onTaskClick: (t: Task) => void }) {
  const { setNodeRef, isOver } = useDroppable({ id })
  return (
    <div ref={setNodeRef} className={`flex-1 min-w-0 rounded-2xl p-3 space-y-2 transition-colors ${isOver ? "bg-gray-100" : "bg-gray-50/60"}`}>
      <div className="flex items-center justify-between px-1">
        <span className="text-xs font-bold text-gray-500 uppercase tracking-wide">{label}</span>
        <span className="text-xs text-gray-400">{items.length}</span>
      </div>
      {items.map(it => (
        <Card key={it.task.id} item={it} onClick={() => onTaskClick(it.task)} />
      ))}
      {items.length === 0 && <p className="text-xs text-gray-300 px-1 py-6 text-center">—</p>}
    </div>
  )
}

export default function AcuerdosBoard({
  plan, onMoveTask, onTaskClick,
}: {
  plan: AnnualPlan
  onMoveTask: (taskId: string, status: Task["status"]) => void
  onTaskClick: (task: Task) => void
}) {
  const [warn, setWarn] = useState<string | null>(null)
  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 4 } }))

  const items: Item[] = plan.months.flatMap(m =>
    m.objectives.flatMap(o => o.tasks.map(t => ({ task: t, month: m }))))

  const onDragEnd = (e: DragEndEvent) => {
    const id = String(e.active.id)
    const over = e.over ? String(e.over.id) : null
    if (!over) return
    const item = items.find(it => it.task.id === id)
    if (!item) return
    if (!COLUMNS.some(c => c.id === over)) return
    if (over === item.task.status) return
    if (over === "completada" && item.task.evidence_count === 0) {
      setWarn("Sube evidencia para validar este acuerdo (abre la tarjeta).")
      return
    }
    setWarn(null)
    onMoveTask(id, over as Task["status"])
  }

  return (
    <div className="space-y-3">
      {warn && <p className="text-xs text-red-500">{warn}</p>}
      <DndContext sensors={sensors} onDragEnd={onDragEnd}>
        <div className="flex gap-3 items-start">
          {COLUMNS.map(c => (
            <Column
              key={c.id} id={c.id} label={c.label}
              items={items.filter(it => it.task.status === c.id)}
              onTaskClick={onTaskClick}
            />
          ))}
        </div>
      </DndContext>
    </div>
  )
}
```

- [ ] **Step 3: Wire the toggle + board into the plan page.** In `frontend/src/app/dashboard/plan/page.tsx`:

  1. Add the import near the other plan-component imports:
  ```typescript
  import AcuerdosBoard from "@/components/plan/AcuerdosBoard"
  ```

  2. Add state near the other `useState` hooks (e.g. after `selectedMonth`):
  ```typescript
  const [boardView, setBoardView] = useState<"meses" | "tablero">("meses")
  ```

  3. In the `active` view (around the block that renders `<MonthTimeline .../>` and `<MonthDetail .../>`), add a toggle ABOVE that block and make the Meses content conditional. Read the file to find the exact JSX; the result should be:
  ```tsx
        <div className="flex gap-1.5 mb-4">
          {(["meses", "tablero"] as const).map(v => (
            <button
              key={v}
              onClick={() => setBoardView(v)}
              className={`text-xs font-medium px-3 py-1.5 rounded-lg transition-colors ${
                boardView === v
                  ? "bg-[var(--gob-navy)] text-[var(--gob-bone)]"
                  : "text-gray-500 hover:bg-gray-100"
              }`}
            >
              {v === "meses" ? "Meses" : "Tablero de acuerdos"}
            </button>
          ))}
        </div>

        {boardView === "tablero" ? (
          <AcuerdosBoard
            plan={plan}
            onMoveTask={(taskId, status) => onUpdateTask(taskId, { status })}
            onTaskClick={setOpenTask}
          />
        ) : (
          <>
            {/* existing MonthTimeline + MonthDetail block goes here, unchanged */}
          </>
        )}
  ```
  Keep the existing `<MonthTimeline .../>` and `<MonthDetail .../>` exactly as they are, just moved inside the `else` branch (`<> ... </>`). The `TaskDrawer` block (`{openTask && (...)}`) stays OUTSIDE this conditional (it already is, after the active-view block) so it works for both views. `plan` is non-null in the active view (guard already exists above).

  Read the file carefully to keep all existing props/handlers intact.

- [ ] **Step 4: Typecheck, lint, build:**
```bash
cd frontend && npx tsc --noEmit && npx eslint src/components/plan/AcuerdosBoard.tsx && npm run build
```
Expected: TSC OK, lint clean, `✓ Compiled successfully`. Fix only errors in new code.

- [ ] **Step 5: Commit:**
```bash
git add frontend/src/lib/annualPlan.ts frontend/src/components/plan/AcuerdosBoard.tsx frontend/src/app/dashboard/plan/page.tsx
git commit -m "feat(b3b): Tablero de Acuerdos (board Monday) en /dashboard/plan"
```

---

## Done criteria

- `GET /annual-plan` devuelve `evidence_count` por tarea.
- El dueño cambia entre "Meses" y "Tablero", arrastra acuerdos entre columnas, y no puede soltar en "Validado" sin evidencia (aviso).
- Las tarjetas muestran 📎 + conteo; el click abre el drawer.
- Suite backend verde; `tsc` + `npm run build` verdes.

## Notes for the implementer

- **El board no tiene estado local de tareas:** deriva las columnas del `plan` que la página actualiza optimistamente (`onUpdateTask` → `patchTaskLocal` → `setPlan`). Al soltar, `onMoveTask` actualiza el plan y la tarjeta re-renderiza en su nueva columna. No agregues estado de board para el movimiento.
- **Gate del front:** evita el request cuando el destino es `completada` y `evidence_count === 0`. Si el conteo está desactualizado y el server responde 409, el `catch` de `onUpdateTask` ya recarga el plan (`loadPlan`).
- **created_at en tests backend:** `ActionTask` tiene `created_at` server_default (None en construcción); el test lo setea a mano en el objeto. Igual para el plan, pero `MonthlyPlanOut`/`ObjectiveOut`/`AnnualPlanOut` no piden `created_at`, así que solo la tarea lo necesita.
- **Sin migración** (la tabla `evidences` ya existe; `evidence_count` es derivado).
