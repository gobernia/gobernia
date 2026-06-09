# Motor de Orden del Día por Señales (nodo 4, V1) · Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Una Agenda priorizada de 5-7 temas del mes (con racional + evidencia) que fusiona los temas de cobertura programados y las señales detectadas (KPI desviado, acuerdos vencidos/por vencer).

**Architecture:** Un servicio puro `agenda_engine.build_agenda` corre detectores sobre el EstadoMes (en vivo), puntúa y rankea. Un endpoint `GET /annual-plan/agenda` reúne los datos y devuelve la lista. El frontend muestra un panel "Agenda del mes" arriba del plan.

**Tech Stack:** FastAPI, SQLAlchemy async, Pydantic v2, pytest (asyncio, db mockeada), Next.js 16 + TS.

**Spec:** `docs/superpowers/specs/2026-06-09-motor-orden-del-dia-senales-design.md`

**Patrones existentes (verificados):**
- `scheduled_for_session(themes, month_index)` → `{"permanente": [BoardTheme], "cobertura": [BoardTheme]}`.
- `coverage_rows(themes, months, active_index)` (B4) → dicts `{key,label,type,frecuencia_anual,esperadas,realizadas,estado}`.
- `ActionTask` tiene `.title`, `.status`, `.due_date` (date|None).
- Router `annual_plan/router.py` ya importa `_current_plan`, `_tasks_by_objective`, `BoardTheme`, `MonthlyPlan`, `select`, `selectinload`, `compute_active_month_index`, `coverage_rows`, `scheduled_for_session`, `date`. KPIs del último mes `done`: `(m.review or {}).get("signals", {}).get("kpis")`.
- Endpoint análogo ya hecho: `GET /annual-plan/alertas` (B6) — mismo patrón de reunión de datos.
- Frontend: `/dashboard/plan` (vista activa) tiene `<AlertsPanel />` arriba del toggle; el nuevo panel va ARRIBA de `<AlertsPanel />`.

---

### Task 1: Servicio `agenda_engine.build_agenda`

**Files:**
- Create: `backend/app/services/governance/agenda_engine.py`
- Test: `backend/tests/unit/test_agenda_engine.py`

- [ ] **Step 1: Write the failing test** at `backend/tests/unit/test_agenda_engine.py`:
```python
from datetime import date, timedelta
from types import SimpleNamespace

from app.services.governance.agenda_engine import build_agenda

TODAY = date(2026, 6, 15)


def _task(title, status, due):
    return SimpleNamespace(title=title, status=status, due_date=due)


def _theme(key, label):
    return SimpleNamespace(key=key, label=label)


def test_kpi_detector_solo_off_track():
    kpis = [
        {"label": "Margen", "value": 8, "target": 15, "unit": "%", "on_track": False},
        {"label": "Liquidez", "value": 2, "target": 1, "unit": "x", "on_track": True},
    ]
    ag = build_agenda([], [], kpis, [], TODAY)
    kpi = [i for i in ag if i["detector"] == "DesviaciónKPI"]
    assert len(kpi) == 1
    assert "Margen" in kpi[0]["titulo"]
    assert kpi[0]["impacto"] == "alto"
    assert kpi[0]["evidencia"]


def test_compromiso_vencido_agregado():
    tasks = [
        _task("Pagar X", "pendiente", TODAY - timedelta(days=3)),
        _task("Hecho", "completada", TODAY - timedelta(days=3)),  # no cuenta
    ]
    ag = build_agenda([], [], [], tasks, TODAY)
    item = next(i for i in ag if i["detector"] == "CompromisoVencido")
    assert "1 acuerdo" in item["titulo"]
    assert item["urgencia"] == "alta"


def test_compromiso_por_vencer():
    tasks = [_task("Y", "en_progreso", TODAY + timedelta(days=3))]
    ag = build_agenda([], [], [], tasks, TODAY)
    assert any(i["detector"] == "CompromisoPorVencer" for i in ag)


def test_cobertura_critico_boost():
    themes = [_theme("aud", "Auditoría")]
    rows = [{"key": "aud", "label": "Auditoría", "esperadas": 4, "realizadas": 0, "estado": "critico"}]
    ag = build_agenda(themes, rows, [], [], TODAY)
    item = next(i for i in ag if i["detector"] == "TemaDeCobertura")
    assert item["score"] == 30.0
    assert item["urgencia"] == "alta"
    assert item["impacto"] == "alto"


def test_orden_por_score():
    themes = [_theme("fin", "Finanzas")]  # cobertura en_tiempo -> 10
    rows = [{"key": "fin", "label": "Finanzas", "esperadas": 1, "realizadas": 1, "estado": "en_tiempo"}]
    kpis = [{"label": "Margen", "value": 8, "target": 15, "unit": "%", "on_track": False}]  # 30
    ag = build_agenda(themes, rows, kpis, [], TODAY)
    assert ag[0]["detector"] == "DesviaciónKPI"
    assert ag[0]["orden"] == 1


def test_max_7():
    themes = [_theme(f"t{i}", f"Tema {i}") for i in range(10)]
    rows = [{"key": f"t{i}", "label": f"Tema {i}", "esperadas": 0, "realizadas": 0, "estado": "en_tiempo"} for i in range(10)]
    ag = build_agenda(themes, rows, [], [], TODAY)
    assert len(ag) == 7
    assert [i["orden"] for i in ag] == list(range(1, 8))


def test_vacio():
    assert build_agenda([], [], [], [], TODAY) == []
```

- [ ] **Step 2: Run it, verify it FAILS** (`ModuleNotFoundError`):
`cd backend && venv/bin/python -m pytest tests/unit/test_agenda_engine.py -v`

- [ ] **Step 3: Implement** `backend/app/services/governance/agenda_engine.py`:
```python
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
```

- [ ] **Step 4: Run the test, verify it PASSES** (7 passed).

- [ ] **Step 5: Commit:**
```bash
git add backend/app/services/governance/agenda_engine.py backend/tests/unit/test_agenda_engine.py
git commit -m "feat(agenda): motor build_agenda (detectores + scoring + ranking)"
```

---

### Task 2: Esquema `AgendaItem` + endpoint `/agenda`

**Files:**
- Create: `backend/app/schemas/agenda.py`
- Modify: `backend/app/api/v1/annual_plan/router.py` (imports + endpoint al final)
- Test: `backend/tests/integration/test_agenda_api.py`

- [ ] **Step 1: Write the failing test** at `backend/tests/integration/test_agenda_api.py`:
```python
import uuid
from datetime import date
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.models.board_theme import BoardTheme
from app.core.dependencies import get_current_user_id, get_db

MOCK_USER_ID = "user_test_agenda"


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
async def test_get_agenda():
    plan = MagicMock(); plan.id = uuid.uuid4(); plan.user_id = MOCK_USER_ID
    plan.start_date = date(2020, 1, 1)  # mes activo = 12 (cap) -> hay meses pasados
    month = MagicMock()
    month.id = uuid.uuid4(); month.month_index = 1
    month.objectives = []; month.covered_themes = []
    month.status = "active"; month.review = None
    themes = [_theme("fin", "permanente", 1, 0)]  # programado en toda sesión; sin cubrir -> crítico

    r1 = MagicMock(); r1.scalar_one_or_none.return_value = plan          # _current_plan
    r2 = MagicMock(); r2.scalars.return_value.all.return_value = [month] # months
    r3 = MagicMock(); r3.scalars.return_value.all.return_value = themes  # themes (sin objetivos -> sin query de tasks)
    db = AsyncMock(); db.execute = AsyncMock(side_effect=[r1, r2, r3])

    app.dependency_overrides[get_db] = _db_override(db)
    app.dependency_overrides[get_current_user_id] = _user_override
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.get("/api/v1/annual-plan/agenda")
    finally:
        app.dependency_overrides.clear()

    assert r.status_code == 200
    body = r.json()
    assert isinstance(body, list)
    assert any(i["detector"] == "TemaDeCobertura" for i in body)
    assert body[0]["orden"] == 1
```

- [ ] **Step 2: Run it, verify it FAILS** (endpoint/schema no existen):
`cd backend && venv/bin/python -m pytest tests/integration/test_agenda_api.py -v`

- [ ] **Step 3: Create the schema** `backend/app/schemas/agenda.py`:
```python
from pydantic import BaseModel


class AgendaItem(BaseModel):
    orden: int
    titulo: str
    area: str
    detector: str
    impacto: str
    urgencia: str
    racional: str
    evidencia: list[str]
    score: float
```

- [ ] **Step 4: Add imports** to `backend/app/api/v1/annual_plan/router.py` (con los otros imports):
```python
from app.schemas.agenda import AgendaItem
from app.services.governance.agenda_engine import build_agenda
```

- [ ] **Step 5: Add the endpoint at the END of the router file:**
```python
# ── Agenda del mes (Motor de Orden del Día por señales) ───────────────────────

@router.get("/annual-plan/agenda", response_model=list[AgendaItem])
async def get_agenda(
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
    sched = scheduled_for_session(themes, active)
    scheduled_themes = list(sched["permanente"]) + list(sched["cobertura"])
    rows = coverage_rows(themes, months, active)

    kpi_signals: list = []
    done = [m for m in months if m.status == "done" and m.review]
    if done:
        latest = max(done, key=lambda m: m.month_index)
        kpi_signals = ((latest.review or {}).get("signals") or {}).get("kpis") or []

    agenda = build_agenda(scheduled_themes, rows, kpi_signals, tasks, date.today())
    return [AgendaItem(**a) for a in agenda]
```

- [ ] **Step 6: Run the test, verify it PASSES** (1 passed):
`cd backend && venv/bin/python -m pytest tests/integration/test_agenda_api.py -v`

- [ ] **Step 7: Run the full backend suite (no regressions):**
`cd backend && venv/bin/python -m pytest -q`

- [ ] **Step 8: Commit:**
```bash
git add backend/app/schemas/agenda.py backend/app/api/v1/annual_plan/router.py backend/tests/integration/test_agenda_api.py
git commit -m "feat(agenda): endpoint /annual-plan/agenda"
```

---

### Task 3: Frontend — panel "Agenda del mes"

**Files:**
- Create: `frontend/src/lib/agenda.ts`
- Create: `frontend/src/components/plan/AgendaPanel.tsx`
- Modify: `frontend/src/app/dashboard/plan/page.tsx` (montar arriba de `<AlertsPanel />`)

- [ ] **Step 1: Create the lib** `frontend/src/lib/agenda.ts`:
```typescript
import api from "@/lib/api"

export interface AgendaItem {
  orden: number
  titulo: string
  area: string
  detector: string
  impacto: string
  urgencia: string
  racional: string
  evidencia: string[]
  score: number
}

export async function getAgenda(): Promise<AgendaItem[]> {
  const r = await api.get<AgendaItem[]>("/annual-plan/agenda")
  return r.data
}
```

- [ ] **Step 2: Create the panel** `frontend/src/components/plan/AgendaPanel.tsx`:
```tsx
"use client"

import { useEffect, useState } from "react"
import { AgendaItem, getAgenda } from "@/lib/agenda"

const CHIP: Record<string, string> = {
  alto: "bg-red-100 text-red-700", alta: "bg-red-100 text-red-700",
  medio: "bg-amber-100 text-amber-700", media: "bg-amber-100 text-amber-700",
  bajo: "bg-gray-100 text-gray-500", baja: "bg-gray-100 text-gray-500",
}

export default function AgendaPanel() {
  const [items, setItems] = useState<AgendaItem[] | null>(null)

  useEffect(() => {
    let active = true
    getAgenda().then(a => { if (active) setItems(a) }).catch(() => { if (active) setItems([]) })
    return () => { active = false }
  }, [])

  if (items === null) return null
  if (items.length === 0) return null

  return (
    <div className="mb-4 rounded-2xl border border-gray-100 bg-white p-4">
      <h3 className="text-sm font-bold text-black uppercase tracking-wide mb-3">Agenda del mes</h3>
      <ol className="space-y-3">
        {items.map(i => (
          <li key={i.orden} className="flex gap-3">
            <span className="flex-shrink-0 w-6 h-6 rounded-full bg-[var(--gob-navy)] text-[var(--gob-bone)] text-xs font-bold flex items-center justify-center">
              {i.orden}
            </span>
            <div className="min-w-0">
              <div className="flex items-center gap-2 flex-wrap">
                <span className="text-sm font-medium text-black">{i.titulo}</span>
                <span className={`text-[10px] font-medium px-1.5 py-0.5 rounded ${CHIP[i.impacto] ?? CHIP.bajo}`}>
                  impacto {i.impacto}
                </span>
                <span className={`text-[10px] font-medium px-1.5 py-0.5 rounded ${CHIP[i.urgencia] ?? CHIP.baja}`}>
                  urgencia {i.urgencia}
                </span>
              </div>
              <p className="text-xs text-gray-500 mt-0.5">{i.racional}</p>
              {i.evidencia.map((e, k) => (
                <p key={k} className="text-xs text-gray-400 mt-0.5">· {e}</p>
              ))}
            </div>
          </li>
        ))}
      </ol>
    </div>
  )
}
```

- [ ] **Step 3: Mount it above AlertsPanel.** Read `frontend/src/app/dashboard/plan/page.tsx`. In the active view it renders `<AlertsPanel />` just before the toggle row. Add the import:
```typescript
import AgendaPanel from "@/components/plan/AgendaPanel"
```
And render `<AgendaPanel />` immediately BEFORE `<AlertsPanel />` (so la Agenda es lo primero). Read the file to place it precisely and keep `<AlertsPanel />` + the toggle + branches unchanged.

- [ ] **Step 4: Typecheck, lint, build:**
```bash
cd frontend && npx tsc --noEmit && npx eslint src/lib/agenda.ts src/components/plan/AgendaPanel.tsx && npm run build
```
Expected: TSC OK, lint clean, `✓ Compiled successfully`. Fix only errors in new code.

- [ ] **Step 5: Commit:**
```bash
git add frontend/src/lib/agenda.ts frontend/src/components/plan/AgendaPanel.tsx frontend/src/app/dashboard/plan/page.tsx
git commit -m "feat(agenda): panel Agenda del mes arriba del plan"
```

---

## Done criteria

- `GET /annual-plan/agenda` devuelve 5-7 temas priorizados con racional + evidencia, fusionando cobertura y señales.
- El panel "Agenda del mes" aparece arriba del plan (sobre Alertas).
- Suite backend verde; `tsc` + `npm run build` verdes.

## Notes for the implementer

- **Sin migración** (cálculo en vivo).
- **`scheduled_for_session` devuelve `{"permanente": [...], "cobertura": [...]}`** — la agenda usa la unión de ambas.
- El endpoint reúne datos **igual que `/alertas`** (B6); reusa los imports ya presentes.
- `list.sort(..., reverse=True)` es **estable**: ante empate de score se respeta el orden de inserción (KPIs → vencidos → por vencer → cobertura).
