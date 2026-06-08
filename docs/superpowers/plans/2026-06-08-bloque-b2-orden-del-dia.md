# Bloque B2 — Calendario de Cobertura + Orden del Día · Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Computar de forma determinista qué temas (de B1) tocan en cada sesión y exponer la orden del día de cada mes (temas programados + objetivos del mes) en el dashboard.

**Architecture:** Un motor sin estado (`coverage_calendar.py`) distribuye los temas activos sobre las 12 sesiones con una regla balanceada/escalonada. Un endpoint nuevo arma la orden del día por mes (sin tabla nueva — derivado). El frontend muestra un panel "Orden del día" al inicio del detalle de cada mes.

**Tech Stack:** FastAPI, SQLAlchemy async, Pydantic v2, pytest (asyncio, db mockeada), Next.js 16 + TypeScript, axios.

**Spec:** `docs/superpowers/specs/2026-06-08-bloque-b2-orden-del-dia-design.md`

---

### Task 1: Motor `coverage_calendar`

**Files:**
- Create: `backend/app/services/governance/coverage_calendar.py`
- Test: `backend/tests/unit/test_coverage_calendar.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/unit/test_coverage_calendar.py
from app.models.board_theme import BoardTheme
from app.services.governance.default_themes import DEFAULT_THEMES
from app.services.governance.coverage_calendar import theme_sessions, scheduled_for_session


def _default_themes():
    return [
        BoardTheme(key=t["key"], label=t["label"], type=t["type"],
                   every_n_sessions=t["every_n_sessions"], active=True, order_index=i)
        for i, t in enumerate(DEFAULT_THEMES)
    ]


def _by_key():
    return {t.key: sessions for t, sessions in theme_sessions(_default_themes())}


def test_permanentes_en_todas_las_sesiones():
    by_key = _by_key()
    assert by_key["resultados_financieros"] == list(range(1, 13))
    assert by_key["riesgos_criticos"] == list(range(1, 13))


def test_bimestrales_escalonados():
    by_key = _by_key()
    assert by_key["talento_sucesion"] == [1, 3, 5, 7, 9, 11]
    assert by_key["tecnologia_ciberseguridad"] == [2, 4, 6, 8, 10, 12]


def test_trimestrales_tres_vias():
    by_key = _by_key()
    assert by_key["auditoria"] == [1, 4, 7, 10]
    assert by_key["cumplimiento_normativo"] == [2, 5, 8, 11]
    assert by_key["esg"] == [3, 6, 9, 12]


def test_semestral_y_anuales():
    by_key = _by_key()
    assert by_key["planeacion_estrategica"] == [1, 7]
    assert by_key["evaluacion_dg"] == [12]
    assert by_key["evaluacion_consejo"] == [11]


def test_inactivos_excluidos():
    themes = _default_themes()
    themes[5].active = False  # talento_sucesion (order_index 5)
    keys = {t.key for t, _ in theme_sessions(themes)}
    assert "talento_sucesion" not in keys


def test_scheduled_for_session_mes_1():
    sched = scheduled_for_session(_default_themes(), 1)
    perm = {t.key for t in sched["permanente"]}
    cob = {t.key for t in sched["cobertura"]}
    assert perm == {"seguimiento_acuerdos", "resultados_financieros",
                    "resultados_operativos", "kpis_estrategicos", "riesgos_criticos"}
    # mes 1: auditoria, talento, planeacion (cobertura due), NO cumplimiento/esg/tecnologia
    assert "auditoria" in cob and "talento_sucesion" in cob and "planeacion_estrategica" in cob
    assert "cumplimiento_normativo" not in cob and "esg" not in cob and "tecnologia_ciberseguridad" not in cob
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && venv/bin/python -m pytest tests/unit/test_coverage_calendar.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.services.governance.coverage_calendar'`

- [ ] **Step 3: Implement the engine**

```python
# backend/app/services/governance/coverage_calendar.py
"""Motor determinista de cobertura (Bloque B2).
Distribuye los temas activos sobre las N sesiones: permanentes en todas; cobertura
escalonada por grupo de frecuencia; anuales ancladas al cierre del año."""
from app.models.board_theme import BoardTheme


def theme_sessions(
    themes: list[BoardTheme], total_sessions: int = 12,
) -> list[tuple[BoardTheme, list[int]]]:
    """Devuelve (tema, [sesiones]) para cada tema ACTIVO. Determinista, sin DB."""
    out: list[tuple[BoardTheme, list[int]]] = []
    cobertura_by_freq: dict[int, list[BoardTheme]] = {}

    for t in themes:
        if not t.active:
            continue
        if t.type == "permanente":
            out.append((t, list(range(1, total_sessions + 1))))
        elif t.type == "cobertura":
            cobertura_by_freq.setdefault(t.every_n_sessions, []).append(t)
        else:  # emergente
            out.append((t, []))

    for n, group in sorted(cobertura_by_freq.items()):
        group.sort(key=lambda x: x.order_index)
        for i, t in enumerate(group):
            if n == total_sessions:  # anual: anclar al cierre del año
                s = total_sessions - i
                out.append((t, [s] if s >= 1 else []))
            else:
                offset = i % n
                out.append((t, [s for s in range(1, total_sessions + 1) if (s - 1) % n == offset]))

    return out


def scheduled_for_session(
    themes: list[BoardTheme], month_index: int, total_sessions: int = 12,
) -> dict[str, list[BoardTheme]]:
    """Temas activos programados en una sesión, agrupados por tipo y ordenados."""
    permanente: list[BoardTheme] = []
    cobertura: list[BoardTheme] = []
    for t, sessions in theme_sessions(themes, total_sessions):
        if month_index in sessions:
            if t.type == "permanente":
                permanente.append(t)
            elif t.type == "cobertura":
                cobertura.append(t)
    permanente.sort(key=lambda x: x.order_index)
    cobertura.sort(key=lambda x: x.order_index)
    return {"permanente": permanente, "cobertura": cobertura}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && venv/bin/python -m pytest tests/unit/test_coverage_calendar.py -v`
Expected: PASS (6 passed)

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/governance/coverage_calendar.py backend/tests/unit/test_coverage_calendar.py
git commit -m "feat(b2): motor coverage_calendar (distribución determinista de temas)"
```

---

### Task 2: Esquema + endpoint de la Orden del Día

**Files:**
- Create: `backend/app/schemas/orden_del_dia.py`
- Modify: `backend/app/api/v1/annual_plan/router.py` (imports + 1 helper + 1 endpoint al final)
- Test: `backend/tests/integration/test_orden_del_dia_api.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/integration/test_orden_del_dia_api.py
import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.core.dependencies import get_current_user_id, get_db

MOCK_USER_ID = "user_test_orden"


def _theme(key, type_, freq, order, active=True):
    t = MagicMock()
    t.id = uuid.uuid4(); t.key = key; t.label = key.replace("_", " ").title()
    t.type = type_; t.every_n_sessions = freq; t.active = active; t.order_index = order
    return t


def _db_override(db):
    async def override():
        yield db
    return override


async def _user_override():
    return MOCK_USER_ID


@pytest.mark.asyncio
async def test_orden_del_dia_mes_1():
    plan = MagicMock(); plan.id = uuid.uuid4(); plan.user_id = MOCK_USER_ID
    themes = [
        _theme("resultados_financieros", "permanente", 1, 1),
        _theme("auditoria", "cobertura", 3, 7),              # mes 1 -> programado
        _theme("cumplimiento_normativo", "cobertura", 3, 8), # mes 1 -> NO (2,5,8,11)
    ]
    month = MagicMock()
    month.id = uuid.uuid4(); month.month_index = 1
    month.period_year = 2026; month.period_month = 1; month.objectives = []

    r1 = MagicMock(); r1.scalar_one_or_none.return_value = plan          # _current_plan
    r2 = MagicMock(); r2.scalars.return_value.all.return_value = themes  # themes query
    r3 = MagicMock(); r3.scalar_one_or_none.return_value = month         # month query
    db = AsyncMock(); db.execute = AsyncMock(side_effect=[r1, r2, r3])

    app.dependency_overrides[get_db] = _db_override(db)
    app.dependency_overrides[get_current_user_id] = _user_override
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.get("/api/v1/annual-plan/months/1/orden-del-dia")
    finally:
        app.dependency_overrides.clear()

    assert r.status_code == 200
    body = r.json()
    assert body["month_index"] == 1
    assert {t["key"] for t in body["permanent_themes"]} == {"resultados_financieros"}
    assert {t["key"] for t in body["coverage_themes"]} == {"auditoria"}


@pytest.mark.asyncio
async def test_orden_del_dia_404_sin_plan():
    r1 = MagicMock(); r1.scalar_one_or_none.return_value = None
    db = AsyncMock(); db.execute = AsyncMock(side_effect=[r1])
    app.dependency_overrides[get_db] = _db_override(db)
    app.dependency_overrides[get_current_user_id] = _user_override
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.get("/api/v1/annual-plan/months/1/orden-del-dia")
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 404
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && venv/bin/python -m pytest tests/integration/test_orden_del_dia_api.py -v`
Expected: FAIL (endpoint no existe → 404 con detalle distinto / o ModuleNotFoundError del schema)

- [ ] **Step 3: Create the schema**

```python
# backend/app/schemas/orden_del_dia.py
from pydantic import BaseModel, Field

from app.schemas.annual_plan import ObjectiveOut


class ThemeRef(BaseModel):
    key: str
    label: str
    every_n_sessions: int | None = None


class OrdenDelDiaOut(BaseModel):
    month_index: int
    period_year: int
    period_month: int
    permanent_themes: list[ThemeRef] = Field(default_factory=list)
    coverage_themes: list[ThemeRef] = Field(default_factory=list)
    objectives: list[ObjectiveOut] = Field(default_factory=list)
```

- [ ] **Step 4: Add imports to the router**

In `backend/app/api/v1/annual_plan/router.py`, add near the other schema/service imports (e.g. after the `board_theme` imports added in B1):

```python
from app.schemas.orden_del_dia import OrdenDelDiaOut, ThemeRef
from app.services.governance.coverage_calendar import scheduled_for_session
```

(`BoardTheme`, `MonthlyPlan`, `selectinload`, `_current_plan`, `_objective_out`, `_tasks_by_objective` already exist in this file.)

- [ ] **Step 5: Add the helper + endpoint at the END of the router file**

```python
# ── Orden del día (B2) ────────────────────────────────────────────────────────

def _theme_ref(t: BoardTheme) -> ThemeRef:
    return ThemeRef(key=t.key, label=t.label, every_n_sessions=t.every_n_sessions)


@router.get("/annual-plan/months/{month_index}/orden-del-dia", response_model=OrdenDelDiaOut)
async def get_orden_del_dia(
    month_index: int,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    plan = await _current_plan(user_id, db)
    if not plan:
        raise HTTPException(status_code=404, detail="No hay plan generado.")

    res = await db.execute(
        select(BoardTheme).where(BoardTheme.annual_plan_id == plan.id)
    )
    themes = list(res.scalars().all())

    mres = await db.execute(
        select(MonthlyPlan)
        .where(MonthlyPlan.annual_plan_id == plan.id, MonthlyPlan.month_index == month_index)
        .options(selectinload(MonthlyPlan.objectives))
    )
    month = mres.scalar_one_or_none()
    if not month:
        raise HTTPException(status_code=404, detail="Mes no encontrado.")

    sched = scheduled_for_session(themes, month_index)
    grouped = await _tasks_by_objective([o.id for o in month.objectives], db)
    return OrdenDelDiaOut(
        month_index=month.month_index,
        period_year=month.period_year,
        period_month=month.period_month,
        permanent_themes=[_theme_ref(t) for t in sched["permanente"]],
        coverage_themes=[_theme_ref(t) for t in sched["cobertura"]],
        objectives=[_objective_out(o, grouped.get(o.id, [])) for o in month.objectives],
    )
```

- [ ] **Step 6: Run test to verify it passes**

Run: `cd backend && venv/bin/python -m pytest tests/integration/test_orden_del_dia_api.py -v`
Expected: PASS (2 passed)

- [ ] **Step 7: Run the full backend suite (no regressions)**

Run: `cd backend && venv/bin/python -m pytest -q`
Expected: all pass.

- [ ] **Step 8: Commit**

```bash
git add backend/app/schemas/orden_del_dia.py backend/app/api/v1/annual_plan/router.py backend/tests/integration/test_orden_del_dia_api.py
git commit -m "feat(b2): endpoint orden-del-dia por mes (temas programados + objetivos)"
```

---

### Task 3: Frontend — panel "Orden del día" en el detalle del mes

**Files:**
- Create: `frontend/src/lib/ordenDelDia.ts`
- Create: `frontend/src/components/plan/OrdenDelDiaPanel.tsx`
- Modify: `frontend/src/components/plan/MonthDetail.tsx` (montar el panel al inicio)

- [ ] **Step 1: Create the API lib**

```typescript
// frontend/src/lib/ordenDelDia.ts
import api from "@/lib/api"
import type { Objective } from "@/lib/annualPlan"

export interface ThemeRef {
  key: string
  label: string
  every_n_sessions: number | null
}

export interface OrdenDelDia {
  month_index: number
  period_year: number
  period_month: number
  permanent_themes: ThemeRef[]
  coverage_themes: ThemeRef[]
  objectives: Objective[]
}

export async function getOrdenDelDia(monthIndex: number): Promise<OrdenDelDia> {
  const r = await api.get<OrdenDelDia>(`/annual-plan/months/${monthIndex}/orden-del-dia`)
  return r.data
}
```

- [ ] **Step 2: Create the panel component**

```tsx
// frontend/src/components/plan/OrdenDelDiaPanel.tsx
"use client"

import { useEffect, useState } from "react"
import { OrdenDelDia, getOrdenDelDia } from "@/lib/ordenDelDia"
import { FREQ_LABEL } from "@/lib/boardThemes"

export default function OrdenDelDiaPanel({ monthIndex }: { monthIndex: number }) {
  const [orden, setOrden] = useState<OrdenDelDia | null>(null)

  useEffect(() => {
    let active = true
    getOrdenDelDia(monthIndex).then(o => { if (active) setOrden(o) }).catch(() => {})
    return () => { active = false }
  }, [monthIndex])

  if (!orden) return null
  if (orden.permanent_themes.length === 0 && orden.coverage_themes.length === 0) return null

  return (
    <div className="rounded-2xl border border-gray-100 bg-gray-50/60 p-5 space-y-4">
      <h3 className="text-sm font-bold text-black uppercase tracking-wide">Orden del día</h3>

      <div>
        <p className="text-xs font-medium text-gray-400 uppercase mb-1.5">Permanentes</p>
        <ul className="space-y-1">
          {orden.permanent_themes.map(t => (
            <li key={t.key} className="text-sm text-black flex items-center gap-2">
              <span className="w-1.5 h-1.5 rounded-full bg-[var(--gob-navy)] flex-shrink-0" />
              {t.label}
            </li>
          ))}
        </ul>
      </div>

      {orden.coverage_themes.length > 0 && (
        <div>
          <p className="text-xs font-medium text-gray-400 uppercase mb-1.5">Cobertura este mes</p>
          <ul className="space-y-1">
            {orden.coverage_themes.map(t => (
              <li key={t.key} className="text-sm text-black flex items-center gap-2">
                <span className="w-1.5 h-1.5 rounded-full bg-amber-400 flex-shrink-0" />
                {t.label}
                {t.every_n_sessions != null && (
                  <span className="text-xs text-gray-400">· {FREQ_LABEL[t.every_n_sessions]}</span>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}

      {orden.objectives.length > 0 && (
        <div>
          <p className="text-xs font-medium text-gray-400 uppercase mb-1.5">Objetivos del mes</p>
          <ul className="space-y-1">
            {orden.objectives.map(o => (
              <li key={o.id} className="text-sm text-black">
                {o.title}
                {o.kpi_refs.length > 0 && (
                  <span className="text-xs text-gray-400"> · {o.kpi_refs.join(", ")}</span>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 3: Mount the panel at the start of MonthDetail**

In `frontend/src/components/plan/MonthDetail.tsx`, add the import at the top with the other imports:

```typescript
import OrdenDelDiaPanel from "@/components/plan/OrdenDelDiaPanel"
```

Then read the component's returned JSX. After the month header block (the `<div>` that renders the `MONTH_NAMES[...] ... Mes {month.month_index}` line and the `month.focus` heading) and BEFORE the review panel / objectives, insert:

```tsx
      <OrdenDelDiaPanel monthIndex={month.month_index} />
```

Place it so it renders directly under the header, at the top of the month's content. If the exact structure is unclear, read the file and put `<OrdenDelDiaPanel monthIndex={month.month_index} />` as the first child after the header `<div>` closes.

- [ ] **Step 4: Typecheck, lint, build**

Run: `cd frontend && npx tsc --noEmit && npx eslint src/lib/ordenDelDia.ts src/components/plan/OrdenDelDiaPanel.tsx && npm run build`
Expected: TSC OK, lint clean, `✓ Compiled successfully`. Fix any errors in the new code only.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/lib/ordenDelDia.ts frontend/src/components/plan/OrdenDelDiaPanel.tsx frontend/src/components/plan/MonthDetail.tsx
git commit -m "feat(b2): panel Orden del día en el detalle del mes"
```

---

## Done criteria

- El motor computa el calendario determinista correcto (verificado contra el catálogo por defecto en pruebas).
- `GET /annual-plan/months/{n}/orden-del-dia` devuelve temas programados + objetivos del mes.
- El dueño ve la orden del día de cada mes en `/dashboard/plan`.
- Suite backend verde; `tsc` + `npm run build` verdes.

## Notes for the implementer

- **DB mockeada (Task 2):** el endpoint hace 3 `db.execute` en orden (_current_plan → themes → month) cuando el mes no tiene objetivos. Por eso el test usa `db.execute = AsyncMock(side_effect=[r1, r2, r3])`. `_tasks_by_objective([])` NO ejecuta query (retorna `{}`), así que con `objectives=[]` son exactamente 3 llamadas. Si añades un caso con objetivos, agrega un 4º result para el query de tareas.
- **Sin tabla nueva:** B2 es derivado. No toca migraciones ni la DB de prod.
- **Frecuencia 12 = anual:** el motor ancla los anuales al cierre (`total_sessions - i`). Solo aplica a `every_n_sessions == total_sessions`.
