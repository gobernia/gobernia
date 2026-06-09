# Bloque B6 — Alertas sobrias · Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Un panel de alertas factuales (sin gamificación) arriba del plan: acuerdos vencidos/por vencer, temas atrasados/críticos, y KPIs off-track del último cierre.

**Architecture:** Un servicio puro `compute_alerts` deriva las alertas de datos existentes. Un endpoint `GET /annual-plan/alertas` reúne tareas + `coverage_rows` (B4) + los signals del último mes cerrado y devuelve la lista. El frontend muestra un panel sobrio al inicio del plan.

**Tech Stack:** FastAPI, SQLAlchemy async, Pydantic v2, pytest (asyncio, db mockeada), Next.js 16 + TS.

**Spec:** `docs/superpowers/specs/2026-06-08-bloque-b6-alertas-design.md`

**Patrones existentes:**
- `coverage_board.coverage_rows(themes, months, active_index)` (B4) → lista de dicts `{key,label,type,frecuencia_anual,esperadas,realizadas,estado}`.
- Router `app/api/v1/annual_plan/router.py` ya importa: `_current_plan`, `_tasks_by_objective`, `BoardTheme`, `MonthlyPlan`, `select`, `selectinload`, `compute_active_month_index`, `coverage_rows`, `date`. `ActionTask` tiene `.status` y `.due_date`. `MonthlyPlan` tiene `.status` (`done` al cerrar) y `.review` (JSONB; al cerrar guarda `review["signals"]["kpis"]` = lista de `{label,value,target,unit,on_track}`).
- Frontend plan page `src/app/dashboard/plan/page.tsx`: vista activa con un toggle `<div className="flex gap-1.5 mb-4">…</div>` (~línea 268). `OrdenDelDiaPanel`/`AcuerdosBoard`/`CoberturaBoard` viven en `src/components/plan/`.

---

### Task 1: Servicio `compute_alerts`

**Files:**
- Create: `backend/app/services/governance/alerts.py`
- Test: `backend/tests/unit/test_alerts.py`

- [ ] **Step 1: Write the failing test** at `backend/tests/unit/test_alerts.py`:
```python
from datetime import date, timedelta
from types import SimpleNamespace

from app.services.governance.alerts import compute_alerts

TODAY = date(2026, 6, 15)


def _task(status, due):
    return SimpleNamespace(status=status, due_date=due)


def test_acuerdo_vencido_critical():
    a = compute_alerts([_task("pendiente", TODAY - timedelta(days=5))], [], [], TODAY)
    assert any(x["level"] == "critical" and x["category"] == "acuerdo" for x in a)


def test_acuerdo_por_vencer_warning():
    a = compute_alerts([_task("en_progreso", TODAY + timedelta(days=3))], [], [], TODAY)
    assert any(x["category"] == "acuerdo" and "próximos 7 días" in x["message"] for x in a)


def test_completada_no_alerta():
    assert compute_alerts([_task("completada", TODAY - timedelta(days=5))], [], [], TODAY) == []


def test_cobertura_critico_y_atrasado():
    rows = [
        {"label": "Auditoría", "esperadas": 4, "realizadas": 1, "estado": "atrasado"},
        {"label": "Sucesión", "esperadas": 2, "realizadas": 0, "estado": "critico"},
        {"label": "Finanzas", "esperadas": 1, "realizadas": 1, "estado": "en_tiempo"},
    ]
    a = compute_alerts([], rows, [], TODAY)
    levels = {(x["level"], x["category"]) for x in a}
    assert ("critical", "cobertura") in levels
    assert ("warning", "cobertura") in levels
    assert all("Finanzas" not in x["message"] for x in a)  # en_tiempo no alerta
    assert a[0]["level"] == "critical"  # críticos primero


def test_kpi_off_track():
    sig = [
        {"label": "Margen", "value": 8, "target": 15, "unit": "%", "on_track": False},
        {"label": "Liquidez", "value": 2, "target": 1, "unit": "x", "on_track": True},
    ]
    a = compute_alerts([], [], sig, TODAY)
    assert any(x["category"] == "kpi" and "Margen" in x["message"] for x in a)
    assert all("Liquidez" not in x["message"] for x in a)


def test_sin_alertas():
    assert compute_alerts([], [], [], TODAY) == []


def test_criticos_antes_que_warnings():
    tasks = [_task("pendiente", TODAY - timedelta(days=1)), _task("pendiente", TODAY + timedelta(days=2))]
    a = compute_alerts(tasks, [], [], TODAY)
    assert a[0]["level"] == "critical"
```

- [ ] **Step 2: Run it, verify it FAILS** (`ModuleNotFoundError`):
`cd backend && venv/bin/python -m pytest tests/unit/test_alerts.py -v`

- [ ] **Step 3: Implement** `backend/app/services/governance/alerts.py`:
```python
"""Alertas sobrias del Consejo (Bloque B6). Determinista, sin DB. Tono factual."""
from datetime import date, timedelta

_ORDER = {"critical": 0, "warning": 1, "info": 2}


def _plural(n: int) -> str:
    return "s" if n != 1 else ""


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
```

- [ ] **Step 4: Run the test, verify it PASSES** (7 passed).

- [ ] **Step 5: Commit:**
```bash
git add backend/app/services/governance/alerts.py backend/tests/unit/test_alerts.py
git commit -m "feat(b6): servicio compute_alerts (alertas sobrias derivadas)"
```

---

### Task 2: Esquema `AlertItem` + endpoint `/alertas`

**Files:**
- Create: `backend/app/schemas/alerts.py`
- Modify: `backend/app/api/v1/annual_plan/router.py` (imports + endpoint al final)
- Test: `backend/tests/integration/test_alerts_api.py`

- [ ] **Step 1: Write the failing test** at `backend/tests/integration/test_alerts_api.py`:
```python
import uuid
from datetime import date
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.models.board_theme import BoardTheme
from app.core.dependencies import get_current_user_id, get_db

MOCK_USER_ID = "user_test_alertas"


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
async def test_get_alertas():
    plan = MagicMock(); plan.id = uuid.uuid4(); plan.user_id = MOCK_USER_ID
    plan.start_date = date.today()  # mes activo = 1
    month = MagicMock()
    month.id = uuid.uuid4(); month.month_index = 1
    month.objectives = []; month.covered_themes = []
    month.status = "active"; month.review = None
    themes = [_theme("fin", "permanente", 1, 0)]  # activo=1, no cubierto -> deficit 1 perm -> atrasado

    r1 = MagicMock(); r1.scalar_one_or_none.return_value = plan          # _current_plan
    r2 = MagicMock(); r2.scalars.return_value.all.return_value = [month] # months
    r3 = MagicMock(); r3.scalars.return_value.all.return_value = themes  # themes (no hay objetivos -> sin query de tasks)
    db = AsyncMock(); db.execute = AsyncMock(side_effect=[r1, r2, r3])

    app.dependency_overrides[get_db] = _db_override(db)
    app.dependency_overrides[get_current_user_id] = _user_override
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.get("/api/v1/annual-plan/alertas")
    finally:
        app.dependency_overrides.clear()

    assert r.status_code == 200
    body = r.json()
    assert isinstance(body, list)
    assert any(x["category"] == "cobertura" for x in body)
```

- [ ] **Step 2: Run it, verify it FAILS** (endpoint/schema no existen):
`cd backend && venv/bin/python -m pytest tests/integration/test_alerts_api.py -v`

- [ ] **Step 3: Create the schema** `backend/app/schemas/alerts.py`:
```python
from pydantic import BaseModel


class AlertItem(BaseModel):
    level: str
    category: str
    message: str
```

- [ ] **Step 4: Add imports** to `backend/app/api/v1/annual_plan/router.py` (con los otros imports):
```python
from app.schemas.alerts import AlertItem
from app.services.governance.alerts import compute_alerts
```

- [ ] **Step 5: Add the endpoint at the END of the router file:**
```python
# ── Alertas (B6) ──────────────────────────────────────────────────────────────

@router.get("/annual-plan/alertas", response_model=list[AlertItem])
async def get_alertas(
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    plan = await _current_plan(user_id, db)
    if not plan:
        raise HTTPException(status_code=404, detail="No hay plan generado.")

    mres = await db.execute(
        select(MonthlyPlan)
        .where(MonthlyPlan.annual_plan_id == plan.id)
        .options(selectinload(MonthlyPlan.objectives))
    )
    months = list(mres.scalars().all())
    obj_ids = [o.id for m in months for o in m.objectives]
    grouped = await _tasks_by_objective(obj_ids, db)
    tasks = [t for ts in grouped.values() for t in ts]

    tres = await db.execute(select(BoardTheme).where(BoardTheme.annual_plan_id == plan.id))
    themes = list(tres.scalars().all())
    active = compute_active_month_index(plan.start_date, date.today())
    rows = coverage_rows(themes, months, active)

    kpi_signals: list = []
    done = [m for m in months if m.status == "done" and m.review]
    if done:
        latest = max(done, key=lambda m: m.month_index)
        kpi_signals = ((latest.review or {}).get("signals") or {}).get("kpis") or []

    alerts = compute_alerts(tasks, rows, kpi_signals, date.today())
    return [AlertItem(**a) for a in alerts]
```

- [ ] **Step 6: Run the test, verify it PASSES** (1 passed):
`cd backend && venv/bin/python -m pytest tests/integration/test_alerts_api.py -v`

- [ ] **Step 7: Run the full backend suite (no regressions):**
`cd backend && venv/bin/python -m pytest -q`

- [ ] **Step 8: Commit:**
```bash
git add backend/app/schemas/alerts.py backend/app/api/v1/annual_plan/router.py backend/tests/integration/test_alerts_api.py
git commit -m "feat(b6): endpoint /annual-plan/alertas"
```

---

### Task 3: Frontend — panel de Alertas

**Files:**
- Create: `frontend/src/lib/alerts.ts`
- Create: `frontend/src/components/plan/AlertsPanel.tsx`
- Modify: `frontend/src/app/dashboard/plan/page.tsx` (montar el panel arriba del toggle)

- [ ] **Step 1: Create the lib** `frontend/src/lib/alerts.ts`:
```typescript
import api from "@/lib/api"

export type AlertLevel = "critical" | "warning" | "info"

export interface AlertItem {
  level: AlertLevel
  category: string
  message: string
}

export async function getAlertas(): Promise<AlertItem[]> {
  const r = await api.get<AlertItem[]>("/annual-plan/alertas")
  return r.data
}
```

- [ ] **Step 2: Create the panel** `frontend/src/components/plan/AlertsPanel.tsx`:
```tsx
"use client"

import { useEffect, useState } from "react"
import { AlertItem, AlertLevel, getAlertas } from "@/lib/alerts"

const BORDER: Record<AlertLevel, string> = {
  critical: "border-red-400 bg-red-50/50",
  warning: "border-amber-400 bg-amber-50/50",
  info: "border-gray-300 bg-gray-50",
}

export default function AlertsPanel() {
  const [alerts, setAlerts] = useState<AlertItem[]>([])

  useEffect(() => {
    let active = true
    getAlertas().then(a => { if (active) setAlerts(a) }).catch(() => {})
    return () => { active = false }
  }, [])

  if (alerts.length === 0) return null

  return (
    <div className="space-y-2 mb-4">
      {alerts.map((a, i) => (
        <div
          key={i}
          className={`text-sm text-gray-700 border-l-4 rounded-r-lg px-3 py-2 ${BORDER[a.level] ?? BORDER.info}`}
        >
          {a.message}
        </div>
      ))}
    </div>
  )
}
```

- [ ] **Step 3: Mount the panel above the toggle.** Read `frontend/src/app/dashboard/plan/page.tsx`. In the `active` view, find the toggle row (`<div className="flex gap-1.5 mb-4">` that maps over `["meses","tablero","cobertura"]`). Add the import:
```typescript
import AlertsPanel from "@/components/plan/AlertsPanel"
```
And render `<AlertsPanel />` immediately BEFORE that toggle `<div>` (so alerts are the first thing in the active view). Read the file to place it precisely and keep the toggle + branches unchanged.

- [ ] **Step 4: Typecheck, lint, build:**
```bash
cd frontend && npx tsc --noEmit && npx eslint src/lib/alerts.ts src/components/plan/AlertsPanel.tsx && npm run build
```
Expected: TSC OK, lint clean, `✓ Compiled successfully`. Fix only errors in new code.

- [ ] **Step 5: Commit:**
```bash
git add frontend/src/lib/alerts.ts frontend/src/components/plan/AlertsPanel.tsx frontend/src/app/dashboard/plan/page.tsx
git commit -m "feat(b6): panel de Alertas arriba del plan"
```

---

## Done criteria

- `GET /annual-plan/alertas` devuelve alertas factuales derivadas.
- El panel de Alertas aparece al inicio del plan (tono sobrio, color por nivel).
- Suite backend verde; `tsc` + `npm run build` verdes.

## Notes for the implementer

- **Sin migración** (B6 no toca DB).
- **El endpoint NO consulta el último mes con query extra:** itera los `months` ya cargados (en memoria) para encontrar el más reciente `done` con `review`.
- **`coverage_rows` y `compute_active_month_index` ya están importados** en el router (de B4); no los dupliques.
- **`compute_active_month_index(plan.start_date, date.today())`** usa la fecha real; por eso el test fija `plan.start_date = date.today()` (activo=1) para un resultado determinista.
