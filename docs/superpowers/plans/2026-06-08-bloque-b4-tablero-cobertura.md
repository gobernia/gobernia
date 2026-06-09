# Bloque B4 — Tablero de Cobertura · Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Marcar temas como cubiertos por mes (desde la Orden del Día) y un Tablero de Cobertura con el semáforo (esperadas vs realizadas).

**Architecture:** `covered_themes` (JSONB) en `MonthlyPlan` guarda las keys marcadas por mes. Un motor puro (`coverage_board.py`) calcula esperadas (calendario de B2) / realizadas (marcas) / estado. Endpoints: marcar cobertura, listar cobertura, y `covered_keys` en la orden del día. Frontend: checkboxes en el panel de Orden del Día + tabla "Cobertura".

**Tech Stack:** FastAPI, SQLAlchemy async, Pydantic v2, pytest (asyncio, db mockeada), Next.js 16 + TS.

**Spec:** `docs/superpowers/specs/2026-06-08-bloque-b4-tablero-cobertura-design.md`

**Patrones existentes:**
- `MonthlyPlan` en `app/models/annual_plan.py` (campos: month_index, status, review JSONB…). `JSONB` ya importado ahí.
- B2 `app/services/governance/coverage_calendar.py` → `theme_sessions(themes, total=12)` devuelve `list[(BoardTheme, [sesiones])]` (solo temas `active`). `compute_active_month_index(start_date, today)` en `app/services/ai/annual_plan_generator.py`.
- Router `app/api/v1/annual_plan/router.py`: `_current_plan`, `get_orden_del_dia` (endpoint), `OrdenDelDiaOut` en `app/schemas/orden_del_dia.py`. `from sqlalchemy.orm.attributes import flag_modified` se usa en otros endpoints del repo (etapa4).
- Frontend: `OrdenDelDiaPanel.tsx` (lista temas con `<li key={t.key}>`), `lib/ordenDelDia.ts` (`OrdenDelDia` + `getOrdenDelDia`). Plan page toggle `boardView: "meses" | "tablero"` (~línea 268) con array `["meses","tablero"]` y ternario que renderiza `AcuerdosBoard`.

---

### Task 1: Columna `covered_themes` en `MonthlyPlan`

**Files:**
- Modify: `backend/app/models/annual_plan.py` (`MonthlyPlan`)
- Create: `backend/scripts/add_covered_themes_column.py`
- Test: `backend/tests/unit/test_covered_themes_column.py`

- [ ] **Step 1: Write the failing test** at `backend/tests/unit/test_covered_themes_column.py`:
```python
from app.models import Base
from app.models.annual_plan import MonthlyPlan


def test_monthly_plan_has_covered_themes_column():
    cols = set(Base.metadata.tables["monthly_plans"].columns.keys())
    assert "covered_themes" in cols


def test_monthly_plan_instantiable_with_covered_themes():
    m = MonthlyPlan(month_index=1, period_year=2026, period_month=1, covered_themes=["fin"])
    assert m.covered_themes == ["fin"]
```

- [ ] **Step 2: Run it, verify it FAILS:**
`cd backend && venv/bin/python -m pytest tests/unit/test_covered_themes_column.py -v`

- [ ] **Step 3: Add the column.** In `backend/app/models/annual_plan.py`, inside `MonthlyPlan`, after the `review` column, add:
```python
    # B4 — keys de tema marcados como cubiertos este mes
    covered_themes: Mapped[list | None] = mapped_column(JSONB, nullable=True, default=list)
```

- [ ] **Step 4: Create the migration script** `backend/scripts/add_covered_themes_column.py`:
```python
"""Agrega la columna monthly_plans.covered_themes SIN Alembic (prod usa ALTER directo).
Idempotente (IF NOT EXISTS).

USO (solo cuando el humano lo autorice — toca la DB):
    venv/bin/python -m scripts.add_covered_themes_column
"""
import asyncio

from sqlalchemy import text

from app.db.session import engine


async def main():
    async with engine.begin() as conn:
        await conn.execute(text(
            "ALTER TABLE monthly_plans ADD COLUMN IF NOT EXISTS covered_themes JSONB DEFAULT '[]'::jsonb"
        ))
    await engine.dispose()
    print("OK: columna monthly_plans.covered_themes creada")


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 5: Run the test, verify it PASSES** (2 passed).

- [ ] **Step 6: Commit:**
```bash
git add backend/app/models/annual_plan.py backend/scripts/add_covered_themes_column.py backend/tests/unit/test_covered_themes_column.py
git commit -m "feat(b4): columna covered_themes en MonthlyPlan + script"
```

---

### Task 2: Motor de cobertura (`coverage_board`)

**Files:**
- Create: `backend/app/services/governance/coverage_board.py`
- Test: `backend/tests/unit/test_coverage_board.py`

- [ ] **Step 1: Write the failing test** at `backend/tests/unit/test_coverage_board.py`:
```python
from types import SimpleNamespace

from app.models.board_theme import BoardTheme
from app.services.governance.coverage_board import coverage_status, coverage_rows


def test_status_en_tiempo():
    assert coverage_status("cobertura", 0) == "en_tiempo"
    assert coverage_status("cobertura", -1) == "en_tiempo"


def test_status_cobertura_escala():
    assert coverage_status("cobertura", 1) == "riesgo"
    assert coverage_status("cobertura", 2) == "atrasado"
    assert coverage_status("cobertura", 3) == "critico"


def test_status_permanente_escala_mas_rapido():
    assert coverage_status("permanente", 1) == "atrasado"
    assert coverage_status("permanente", 2) == "critico"


def _theme(key, type_, freq, order, active=True):
    return BoardTheme(key=key, label=key.title(), type=type_,
                      every_n_sessions=freq, active=active, order_index=order)


def test_coverage_rows():
    themes = [
        _theme("fin", "permanente", 1, 0),   # sesiones 1..12
        _theme("aud", "cobertura", 3, 1),    # sesiones 1,4,7,10
    ]
    months = [
        SimpleNamespace(covered_themes=["fin", "aud"]),  # mes 1
        SimpleNamespace(covered_themes=["fin"]),         # mes 2
    ]
    rows = {r["key"]: r for r in coverage_rows(themes, months, active_index=4)}

    # fin: esperadas (1..4) = 4, realizadas = 2, deficit 2, permanente -> critico
    assert rows["fin"]["frecuencia_anual"] == 12
    assert rows["fin"]["esperadas"] == 4
    assert rows["fin"]["realizadas"] == 2
    assert rows["fin"]["estado"] == "critico"
    # aud: sesiones <=4 = {1,4} = 2 esperadas, realizadas 1, deficit 1 -> riesgo
    assert rows["aud"]["frecuencia_anual"] == 4
    assert rows["aud"]["esperadas"] == 2
    assert rows["aud"]["realizadas"] == 1
    assert rows["aud"]["estado"] == "riesgo"
```

- [ ] **Step 2: Run it, verify it FAILS** (`ModuleNotFoundError`).

- [ ] **Step 3: Implement** `backend/app/services/governance/coverage_board.py`:
```python
"""Cálculo del Tablero de Cobertura (Bloque B4). Determinista, sin DB."""
from app.models.board_theme import BoardTheme
from app.services.governance.coverage_calendar import theme_sessions


def coverage_status(theme_type: str, deficit: int) -> str:
    if deficit <= 0:
        return "en_tiempo"
    if theme_type == "permanente":  # escala más rápido (cada sesión cuentan)
        return "atrasado" if deficit == 1 else "critico"
    if deficit == 1:
        return "riesgo"
    if deficit == 2:
        return "atrasado"
    return "critico"


def coverage_rows(themes: list[BoardTheme], months, active_index: int, total_sessions: int = 12) -> list[dict]:
    """`months` = objetos con atributo `covered_themes` (lista de keys o None)."""
    covered_by_key: dict[str, int] = {}
    for m in months:
        for k in (m.covered_themes or []):
            covered_by_key[k] = covered_by_key.get(k, 0) + 1

    rows: list[dict] = []
    for t, sessions in theme_sessions(themes, total_sessions):
        if t.type not in ("permanente", "cobertura"):
            continue
        esperadas = sum(1 for s in sessions if s <= active_index)
        realizadas = covered_by_key.get(t.key, 0)
        rows.append({
            "key": t.key, "label": t.label, "type": t.type,
            "frecuencia_anual": len(sessions),
            "esperadas": esperadas, "realizadas": realizadas,
            "estado": coverage_status(t.type, esperadas - realizadas),
        })
    return rows
```

- [ ] **Step 4: Run the test, verify it PASSES** (4 passed).

- [ ] **Step 5: Commit:**
```bash
git add backend/app/services/governance/coverage_board.py backend/tests/unit/test_coverage_board.py
git commit -m "feat(b4): motor coverage_board (esperadas/realizadas/semáforo)"
```

---

### Task 3: Endpoints — cobertura, marcar, y `covered_keys` en la orden del día

**Files:**
- Create: `backend/app/schemas/coverage.py`
- Modify: `backend/app/schemas/orden_del_dia.py` (`covered_keys`)
- Modify: `backend/app/api/v1/annual_plan/router.py` (imports + 2 endpoints + `covered_keys` en get_orden_del_dia)
- Modify: `backend/tests/integration/test_orden_del_dia_api.py` (el mock del mes necesita `covered_themes`)
- Test: `backend/tests/integration/test_coverage_api.py`

- [ ] **Step 1: Write the failing test** at `backend/tests/integration/test_coverage_api.py`:
```python
import uuid
from datetime import date
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.models.board_theme import BoardTheme
from app.core.dependencies import get_current_user_id, get_db

MOCK_USER_ID = "user_test_cobertura"


def _theme(key, type_, freq, order):
    return BoardTheme(key=key, label=key.title(), type=type_,
                      every_n_sessions=freq, active=True, order_index=order)


def _db_override(db):
    async def override():
        yield db
    return override


async def _user_override():
    return MOCK_USER_ID


@pytest.mark.asyncio
async def test_get_cobertura():
    plan = MagicMock(); plan.id = uuid.uuid4(); plan.user_id = MOCK_USER_ID
    plan.start_date = date.today()  # mes activo = 1
    themes = [_theme("fin", "permanente", 1, 0), _theme("aud", "cobertura", 3, 1)]
    m1 = MagicMock(); m1.covered_themes = ["fin"]

    r1 = MagicMock(); r1.scalar_one_or_none.return_value = plan
    r2 = MagicMock(); r2.scalars.return_value.all.return_value = themes
    r3 = MagicMock(); r3.scalars.return_value.all.return_value = [m1]
    db = AsyncMock(); db.execute = AsyncMock(side_effect=[r1, r2, r3])

    app.dependency_overrides[get_db] = _db_override(db)
    app.dependency_overrides[get_current_user_id] = _user_override
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.get("/api/v1/annual-plan/cobertura")
    finally:
        app.dependency_overrides.clear()

    assert r.status_code == 200
    rows = {row["key"]: row for row in r.json()}
    # activo=1: fin esperadas 1, realizadas 1 -> en_tiempo; aud esperadas 1 (sesión 1), realizadas 0 -> riesgo
    assert rows["fin"]["estado"] == "en_tiempo"
    assert rows["aud"]["esperadas"] == 1
    assert rows["aud"]["estado"] == "riesgo"


@pytest.mark.asyncio
async def test_mark_coverage_adds_key():
    plan = MagicMock(); plan.id = uuid.uuid4(); plan.user_id = MOCK_USER_ID
    plan.start_date = date.today()  # activo = 1
    month = MagicMock(); month.month_index = 1; month.covered_themes = []

    r1 = MagicMock(); r1.scalar_one_or_none.return_value = plan
    r2 = MagicMock(); r2.scalar_one_or_none.return_value = month
    db = AsyncMock(); db.execute = AsyncMock(side_effect=[r1, r2])
    db.flush = AsyncMock(); db.commit = AsyncMock()

    app.dependency_overrides[get_db] = _db_override(db)
    app.dependency_overrides[get_current_user_id] = _user_override
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.post("/api/v1/annual-plan/months/1/coverage",
                             json={"theme_key": "fin", "covered": True})
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 200
    assert "fin" in month.covered_themes


@pytest.mark.asyncio
async def test_mark_coverage_future_month_400():
    plan = MagicMock(); plan.id = uuid.uuid4(); plan.user_id = MOCK_USER_ID
    plan.start_date = date.today()  # activo = 1
    r1 = MagicMock(); r1.scalar_one_or_none.return_value = plan
    db = AsyncMock(); db.execute = AsyncMock(side_effect=[r1])
    app.dependency_overrides[get_db] = _db_override(db)
    app.dependency_overrides[get_current_user_id] = _user_override
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.post("/api/v1/annual-plan/months/6/coverage",
                             json={"theme_key": "fin", "covered": True})
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 400
```

- [ ] **Step 2: Run it, verify it FAILS** (endpoints/schema no existen).

- [ ] **Step 3: Create the schema** `backend/app/schemas/coverage.py`:
```python
from pydantic import BaseModel


class CoverageRow(BaseModel):
    key: str
    label: str
    type: str
    frecuencia_anual: int
    esperadas: int
    realizadas: int
    estado: str


class CoverageMarkIn(BaseModel):
    theme_key: str
    covered: bool
```

- [ ] **Step 4: Add `covered_keys` to `OrdenDelDiaOut`.** In `backend/app/schemas/orden_del_dia.py`, add to `OrdenDelDiaOut` (after `coverage_themes`):
```python
    covered_keys: list[str] = Field(default_factory=list)
```
(`Field` is already imported in that file.)

- [ ] **Step 5: Add imports + populate `covered_keys` in `get_orden_del_dia`.** In `backend/app/api/v1/annual_plan/router.py` add near the other imports:
```python
from datetime import date
from sqlalchemy.orm.attributes import flag_modified
from app.schemas.coverage import CoverageRow, CoverageMarkIn
from app.services.governance.coverage_board import coverage_rows
from app.services.ai.annual_plan_generator import compute_active_month_index
```
(If `date` / `compute_active_month_index` are already imported, don't duplicate.) Then in `get_orden_del_dia`, add `covered_keys=list(month.covered_themes or [])` to the `OrdenDelDiaOut(...)` return (after `coverage_themes=...`):
```python
        coverage_themes=[_theme_ref(t) for t in sched["cobertura"]],
        covered_keys=list(month.covered_themes or []),
        objectives=[_objective_out(o, grouped.get(o.id, [])) for o in month.objectives],
```

- [ ] **Step 6: Add the two endpoints at the END of the router file:**
```python
# ── Cobertura (B4) ────────────────────────────────────────────────────────────

@router.get("/annual-plan/cobertura", response_model=list[CoverageRow])
async def get_cobertura(
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    plan = await _current_plan(user_id, db)
    if not plan:
        raise HTTPException(status_code=404, detail="No hay plan generado.")
    tres = await db.execute(select(BoardTheme).where(BoardTheme.annual_plan_id == plan.id))
    themes = list(tres.scalars().all())
    mres = await db.execute(select(MonthlyPlan).where(MonthlyPlan.annual_plan_id == plan.id))
    months = list(mres.scalars().all())
    active = compute_active_month_index(plan.start_date, date.today())
    return [CoverageRow(**row) for row in coverage_rows(themes, months, active)]


@router.post("/annual-plan/months/{month_index}/coverage")
async def mark_coverage(
    month_index: int,
    body: CoverageMarkIn,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    plan = await _current_plan(user_id, db)
    if not plan:
        raise HTTPException(status_code=404, detail="No hay plan generado.")
    active = compute_active_month_index(plan.start_date, date.today())
    if month_index > active:
        raise HTTPException(status_code=400, detail="No puedes marcar cobertura de una sesión futura.")
    mres = await db.execute(
        select(MonthlyPlan).where(
            MonthlyPlan.annual_plan_id == plan.id, MonthlyPlan.month_index == month_index
        )
    )
    month = mres.scalar_one_or_none()
    if not month:
        raise HTTPException(status_code=404, detail="Mes no encontrado.")
    keys = list(month.covered_themes or [])
    if body.covered and body.theme_key not in keys:
        keys.append(body.theme_key)
    elif not body.covered and body.theme_key in keys:
        keys.remove(body.theme_key)
    month.covered_themes = keys
    flag_modified(month, "covered_themes")
    await db.flush()
    return {"month_index": month_index, "covered_themes": keys}
```

- [ ] **Step 7: Fix the existing orden-del-día test.** In `backend/tests/integration/test_orden_del_dia_api.py`, the `month` MagicMock in `test_orden_del_dia_mes_1` must define `covered_themes` (else `list(month.covered_themes or [])` fails on a MagicMock). Add to that test's month setup:
```python
    month.covered_themes = []
```

- [ ] **Step 8: Run the tests, verify they PASS:**
`cd backend && venv/bin/python -m pytest tests/integration/test_coverage_api.py tests/integration/test_orden_del_dia_api.py -v`

- [ ] **Step 9: Run the full backend suite (no regressions):**
`cd backend && venv/bin/python -m pytest -q`

- [ ] **Step 10: Commit:**
```bash
git add backend/app/schemas/coverage.py backend/app/schemas/orden_del_dia.py backend/app/api/v1/annual_plan/router.py backend/tests/integration/test_coverage_api.py backend/tests/integration/test_orden_del_dia_api.py
git commit -m "feat(b4): endpoints cobertura + marcar + covered_keys en orden del día"
```

---

### Task 4: Frontend — checkboxes + Tablero de Cobertura

**Files:**
- Modify: `frontend/src/lib/ordenDelDia.ts` (`covered_keys` + `markCoverage`)
- Create: `frontend/src/lib/coverage.ts`
- Modify: `frontend/src/components/plan/OrdenDelDiaPanel.tsx` (checkboxes)
- Create: `frontend/src/components/plan/CoberturaBoard.tsx`
- Modify: `frontend/src/app/dashboard/plan/page.tsx` (pestaña "Cobertura")

- [ ] **Step 1: Extend the orden lib.** In `frontend/src/lib/ordenDelDia.ts`, add `covered_keys: string[]` to the `OrdenDelDia` interface (after `coverage_themes`), and add:
```typescript
export async function markCoverage(monthIndex: number, themeKey: string, covered: boolean): Promise<void> {
  await api.post(`/annual-plan/months/${monthIndex}/coverage`, { theme_key: themeKey, covered })
}
```

- [ ] **Step 2: Create the coverage lib** `frontend/src/lib/coverage.ts`:
```typescript
import api from "@/lib/api"

export type CoverageEstado = "en_tiempo" | "riesgo" | "atrasado" | "critico"

export interface CoverageRow {
  key: string
  label: string
  type: string
  frecuencia_anual: number
  esperadas: number
  realizadas: number
  estado: CoverageEstado
}

export async function getCobertura(): Promise<CoverageRow[]> {
  const r = await api.get<CoverageRow[]>("/annual-plan/cobertura")
  return r.data
}
```

- [ ] **Step 3: Add checkboxes to `OrdenDelDiaPanel`.** Read `frontend/src/components/plan/OrdenDelDiaPanel.tsx`. It fetches `orden` (now with `covered_keys`) and renders `permanent_themes`/`coverage_themes` as `<li key={t.key}>`. Make these changes:
  1. Import `markCoverage`:
  ```typescript
  import { OrdenDelDia, getOrdenDelDia, markCoverage } from "@/lib/ordenDelDia"
  ```
  2. Add local state for the covered set, initialized from `orden.covered_keys` when it loads:
  ```typescript
  const [covered, setCovered] = useState<Set<string>>(new Set())
  ```
  In the `useEffect` `.then`, after `setOrden(o)`, also `setCovered(new Set(o.covered_keys))`.
  3. Add a toggle handler:
  ```typescript
  const toggle = (key: string) => {
    const next = new Set(covered)
    const isCovered = next.has(key)
    if (isCovered) next.delete(key); else next.add(key)
    setCovered(next)
    markCoverage(monthIndex, key, !isCovered).catch(() => {
      // revertir en error (p.ej. mes futuro → 400)
      setCovered(prev => {
        const r = new Set(prev)
        if (isCovered) r.add(key); else r.delete(key)
        return r
      })
    })
  }
  ```
  4. In BOTH the permanent and coverage `<li>` renders, add a checkbox before the label so each theme row becomes:
  ```tsx
  <li key={t.key} className="text-sm text-black flex items-center gap-2">
    <input type="checkbox" checked={covered.has(t.key)} onChange={() => toggle(t.key)}
      className="accent-[var(--gob-navy)] cursor-pointer" />
    {/* keep the existing dot + label that were already inside the <li> */}
    ...existing content...
  </li>
  ```
  Keep the existing dot/label markup inside the `<li>` — just prepend the checkbox. Read the file to preserve the current inner content exactly.

- [ ] **Step 4: Create the CoberturaBoard** `frontend/src/components/plan/CoberturaBoard.tsx`:
```tsx
"use client"

import { useEffect, useState } from "react"
import { CoverageRow, CoverageEstado, getCobertura } from "@/lib/coverage"

const ESTADO: Record<CoverageEstado, { label: string; cls: string }> = {
  en_tiempo: { label: "En tiempo", cls: "bg-green-100 text-green-700" },
  riesgo:    { label: "Riesgo",    cls: "bg-amber-100 text-amber-700" },
  atrasado:  { label: "Atrasado",  cls: "bg-orange-100 text-orange-700" },
  critico:   { label: "Crítico",   cls: "bg-red-100 text-red-700" },
}

export default function CoberturaBoard() {
  const [rows, setRows] = useState<CoverageRow[] | null>(null)

  useEffect(() => {
    let active = true
    getCobertura().then(r => { if (active) setRows(r) }).catch(() => { if (active) setRows([]) })
    return () => { active = false }
  }, [])

  if (rows === null) return <p className="text-sm text-gray-400">Cargando cobertura…</p>
  if (rows.length === 0) return <p className="text-sm text-gray-400">Sin temas de cobertura.</p>

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="text-left text-[11px] uppercase tracking-wide text-gray-400 border-b border-gray-100">
            <th className="py-2 pr-4 font-medium">Tema</th>
            <th className="py-2 px-3 font-medium text-center">Frecuencia</th>
            <th className="py-2 px-3 font-medium text-center">Esperadas</th>
            <th className="py-2 px-3 font-medium text-center">Realizadas</th>
            <th className="py-2 pl-3 font-medium">Estado</th>
          </tr>
        </thead>
        <tbody>
          {rows.map(r => {
            const e = ESTADO[r.estado]
            return (
              <tr key={r.key} className="border-b border-gray-50">
                <td className="py-2.5 pr-4 text-black">{r.label}</td>
                <td className="py-2.5 px-3 text-center text-gray-500">{r.frecuencia_anual}</td>
                <td className="py-2.5 px-3 text-center text-gray-500">{r.esperadas}</td>
                <td className="py-2.5 px-3 text-center text-gray-500">{r.realizadas}</td>
                <td className="py-2.5 pl-3">
                  <span className={`inline-block text-[11px] font-medium px-2 py-0.5 rounded-md ${e.cls}`}>{e.label}</span>
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
```

- [ ] **Step 5: Add the "Cobertura" tab in the plan page.** In `frontend/src/app/dashboard/plan/page.tsx`:
  1. Import: `import CoberturaBoard from "@/components/plan/CoberturaBoard"`.
  2. Widen the state type: `const [boardView, setBoardView] = useState<"meses" | "tablero" | "cobertura">("meses")`.
  3. In the toggle array, add `"cobertura"`: change `(["meses", "tablero"] as const)` to `(["meses", "tablero", "cobertura"] as const)`, and extend the label expression so it reads:
  ```tsx
  {v === "meses" ? "Meses" : v === "tablero" ? "Tablero de acuerdos" : "Cobertura"}
  ```
  4. Add a `cobertura` branch to the render. The current shape is `{boardView === "tablero" ? (<AcuerdosBoard .../>) : (<> ...meses... </>)}`. Change it to:
  ```tsx
  {boardView === "tablero" ? (
    <AcuerdosBoard
      plan={plan!}
      onMoveTask={(taskId, status) => onUpdateTask(taskId, { status })}
      onTaskClick={setOpenTask}
    />
  ) : boardView === "cobertura" ? (
    <CoberturaBoard />
  ) : (
    <>
      {/* the EXISTING MonthTimeline + MonthDetail block, unchanged */}
    </>
  )}
  ```
  Read the file to keep the existing `AcuerdosBoard` props and the Meses block exactly as they are.

- [ ] **Step 6: Typecheck, lint, build:**
```bash
cd frontend && npx tsc --noEmit && npx eslint src/lib/coverage.ts src/components/plan/CoberturaBoard.tsx && npm run build
```
Expected: TSC OK, lint clean, `✓ Compiled successfully`. Fix only errors in new code.

- [ ] **Step 7: Commit:**
```bash
git add frontend/src/lib/ordenDelDia.ts frontend/src/lib/coverage.ts frontend/src/components/plan/OrdenDelDiaPanel.tsx frontend/src/components/plan/CoberturaBoard.tsx frontend/src/app/dashboard/plan/page.tsx
git commit -m "feat(b4): checkboxes de cobertura + pestaña Tablero de Cobertura"
```

---

## Done criteria

- Columna `covered_themes` creada (script corrido en prod cuando se autorice).
- El dueño marca temas cubiertos desde la Orden del Día (checkboxes); no puede marcar meses futuros (400).
- `GET /annual-plan/cobertura` devuelve esperadas/realizadas/estado por tema.
- La pestaña "Cobertura" muestra la tabla con semáforo.
- Suite backend verde; `tsc` + `npm run build` verdes.

## Notes for the implementer

- **Migración (manual, autorizada):** tras desplegar, correr en Railway `python -m scripts.add_covered_themes_column`.
- **`covered_themes` server-side:** la columna es `nullable=True default=list`; en código se usa `month.covered_themes or []` para tolerar `None`.
- **El test existente de orden-del-día** debe setear `month.covered_themes = []` en su mock (Task 3 step 7) o el endpoint fallará al serializar un MagicMock.
- **Marcar futuro:** el front revierte el optimismo si el backend responde 400 (mes > activo).
