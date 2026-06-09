# Chair IA sobre la Agenda (capa nodo 4) · Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Un botón "Convocar al Chair" que cura la agenda determinista con Claude (reordena + racional en prosa + carta), la persiste en el mes activo, y se muestra al recargar. Best-effort: sin API key o con fallo → se queda la determinista.

**Architecture:** Servicio sync `chair_curate_agenda` (molde de `run_month_review`) con reconstrucción anti-alucinación + fallback. Columna `chair_agenda` JSONB en `MonthlyPlan`. `GET /annual-plan/agenda` devuelve `AgendaOut {curada, carta, items}` (la curada si está guardada). `POST /annual-plan/agenda/chair` corre el Chair y persiste.

**Tech Stack:** FastAPI, SQLAlchemy async (JSONB), anthropic SDK, anyio.to_thread, pytest, Next.js 16 + TS.

**Spec:** `docs/superpowers/specs/2026-06-09-chair-ia-agenda-design.md`

**Patrones existentes (verificados):**
- `_create_with_retry(client, **kwargs)` y `_build_company_context(memory_buffer)` viven en `app/services/ai/agents/base.py`. `settings.ANTHROPIC_API_KEY` / `settings.AI_MODEL` (importar settings como en `month_review.py`).
- `MonthlyPlan` (`app/models/annual_plan.py`): `review` JSONB (l.62), `covered_themes` JSONB (l.65) — añadir `chair_agenda` tras `covered_themes`.
- Migración aditiva: patrón `scripts/add_covered_themes_column.py` (`engine.begin()` + `ALTER TABLE ... ADD COLUMN IF NOT EXISTS`).
- Router `annual_plan/router.py` YA tiene el endpoint `GET /annual-plan/agenda` (devuelve `list[AgendaItem]`, se refactoriza aquí), e importa: `build_agenda`, `AgendaItem`, `scheduled_for_session`, `coverage_rows`, `compute_active_month_index`, `_current_plan`, `_tasks_by_objective`, `BoardTheme`, `MonthlyPlan`, `select`, `selectinload`, `date`, `_MONTH_NAMES`, `OnboardingSession`, `anyio` (usado en `_run_close`), y `flag_modified as _flag_modified` (de B4).
- `app/services/ai/agenda_chair.py` NO existe (se crea).

---

### Task 1: Servicio `chair_curate_agenda`

**Files:**
- Create: `backend/app/services/ai/agenda_chair.py`
- Test: `backend/tests/unit/test_agenda_chair.py`

- [ ] **Step 1: Write the failing test** at `backend/tests/unit/test_agenda_chair.py`:
```python
import json

from app.services.ai import agenda_chair
from app.services.ai.agenda_chair import chair_curate_agenda, _rebuild

AGENDA = [
    {"orden": 1, "titulo": "A", "area": "kpi", "detector": "DesviaciónKPI",
     "impacto": "alto", "urgencia": "media", "racional": "rac A", "evidencia": ["evA"], "score": 30.0},
    {"orden": 2, "titulo": "B", "area": "cobertura", "detector": "TemaDeCobertura",
     "impacto": "bajo", "urgencia": "baja", "racional": "rac B", "evidencia": ["evB"], "score": 10.0},
]


def test_fallback_sin_api_key(monkeypatch):
    monkeypatch.setattr(agenda_chair.settings, "ANTHROPIC_API_KEY", "")
    out = chair_curate_agenda(AGENDA, {}, "Junio 2026")
    assert out == {"carta": "", "items": AGENDA}


def test_fallback_agenda_vacia(monkeypatch):
    monkeypatch.setattr(agenda_chair.settings, "ANTHROPIC_API_KEY", "sk-test")
    assert chair_curate_agenda([], {}, "Junio 2026") == {"carta": "", "items": []}


def test_rebuild_reordena_y_reescribe():
    raw = json.dumps({"carta": "Bienvenidos.", "prioridad": [1, 0],
                      "racionales": {"1": "nuevo rac B", "0": "nuevo rac A"}})
    out = _rebuild(AGENDA, raw)
    assert out["carta"] == "Bienvenidos."
    assert [i["titulo"] for i in out["items"]] == ["B", "A"]
    assert out["items"][0]["orden"] == 1 and out["items"][1]["orden"] == 2
    assert out["items"][0]["racional"] == "nuevo rac B"
    assert out["items"][0]["evidencia"] == ["evB"]  # evidencia original preservada


def test_rebuild_anexa_faltantes_y_conserva_racional():
    raw = json.dumps({"carta": "", "prioridad": [1], "racionales": {}})
    out = _rebuild(AGENDA, raw)
    assert [i["titulo"] for i in out["items"]] == ["B", "A"]  # 0 anexado al final
    assert out["items"][1]["racional"] == "rac A"  # conserva original si no hay nuevo


def test_rebuild_ignora_ids_invalidos():
    raw = json.dumps({"carta": "", "prioridad": [5, 0, "x", 1], "racionales": {}})
    out = _rebuild(AGENDA, raw)
    assert [i["titulo"] for i in out["items"]] == ["A", "B"]


def test_rebuild_json_envuelto_en_prosa():
    raw = "Claro:\n```json\n" + json.dumps({"carta": "C", "prioridad": [0, 1], "racionales": {}}) + "\n```"
    out = _rebuild(AGENDA, raw)
    assert out["carta"] == "C"
    assert [i["titulo"] for i in out["items"]] == ["A", "B"]
```

- [ ] **Step 2: Run it, verify it FAILS** (`ModuleNotFoundError`):
`cd backend && venv/bin/python -m pytest tests/unit/test_agenda_chair.py -v`

- [ ] **Step 3: Implement** `backend/app/services/ai/agenda_chair.py`:
```python
"""Curaduría del Chair sobre la agenda determinista (capa nodo 4).

Best-effort: sin API key, agenda vacía o cualquier fallo → devuelve la agenda determinista
intacta. Reconstrucción anti-alucinación: el Chair solo reordena y reescribe el racional de
los temas DADOS; nunca inventa temas ni evidencia.
"""
import json

import anthropic

from app.core.config import settings
from app.services.ai.agents.base import _build_company_context, _create_with_retry

_CHAIR_SYSTEM = (
    "Eres el Chair (presidente) de un consejo de administración de una empresa familiar. "
    "Recibes una agenda candidata del mes ya puntuada por un motor de señales. Tu trabajo:\n"
    "1) Decidir el ORDEN REAL de importancia del mes. Puedes subir un tema de bajo score si es "
    "estratégico (p. ej. una señal del sistema familiar) o bajar uno de score alto si es ruido "
    "estacional. Usa tu criterio de consejero, no solo el número.\n"
    "2) Reescribir el racional de cada tema en prosa breve y natural (1-2 frases), citando su "
    "evidencia, como hablaría un consejero real.\n"
    "3) Escribir una 'carta' de apertura de máximo 120 palabras que enmarque el mes con tono "
    "sobrio y directivo.\n"
    "NO inventes temas nuevos ni evidencia: trabaja SOLO con los temas dados (por su id). "
    "Responde ÚNICAMENTE con JSON válido."
)


def chair_curate_agenda(deterministic_agenda: list[dict], memory_buffer: dict, period_label: str) -> dict:
    if not settings.ANTHROPIC_API_KEY or not deterministic_agenda:
        return {"carta": "", "items": deterministic_agenda}

    company_ctx = _build_company_context(memory_buffer or {})
    items_for_llm = [
        {"id": i, "titulo": it["titulo"], "detector": it["detector"],
         "evidencia": it["evidencia"], "score": it["score"]}
        for i, it in enumerate(deterministic_agenda)
    ]
    user_prompt = (
        f"EMPRESA:\n{company_ctx}\n\n"
        f"MES: {period_label}\n\n"
        f"AGENDA CANDIDATA (ya puntuada):\n"
        f"{json.dumps(items_for_llm, ensure_ascii=False, indent=2)}\n\n"
        "Cura la agenda. Responde ÚNICAMENTE con JSON con esta forma exacta:\n"
        '{"carta": "<=120 palabras", "prioridad": [ids en orden de importancia], '
        '"racionales": {"<id>": "1-2 frases en prosa citando la evidencia"}}'
    )
    try:
        client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
        response = _create_with_retry(
            client, model=settings.AI_MODEL, max_tokens=2048,
            system=_CHAIR_SYSTEM,
            messages=[{"role": "user", "content": user_prompt}],
        )
        return _rebuild(deterministic_agenda, response.content[0].text)
    except Exception:
        return {"carta": "", "items": deterministic_agenda}


def _extract_json(text: str) -> str:
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise ValueError("respuesta sin JSON")
    return text[start:end + 1]


def _rebuild(deterministic_agenda: list[dict], raw_text: str) -> dict:
    parsed = json.loads(_extract_json(raw_text))
    carta = str(parsed.get("carta") or "")
    racionales = parsed.get("racionales") or {}
    prioridad = parsed.get("prioridad") or []

    n = len(deterministic_agenda)
    seen: set = set()
    orden_final: list = []
    for pid in prioridad:
        try:
            pid = int(pid)
        except (TypeError, ValueError):
            continue
        if 0 <= pid < n and pid not in seen:
            seen.add(pid)
            orden_final.append(pid)
    for i in range(n):  # anexa los faltantes en su orden original
        if i not in seen:
            orden_final.append(i)

    items: list = []
    for pos, pid in enumerate(orden_final, start=1):
        original = dict(deterministic_agenda[pid])
        original["orden"] = pos
        nuevo = racionales.get(str(pid))
        if nuevo:
            original["racional"] = str(nuevo)
        items.append(original)
    return {"carta": carta, "items": items}
```
(NOTA: si la importación de `settings` difiere, úsala igual que `app/services/ai/month_review.py`.)

- [ ] **Step 4: Run the test, verify it PASSES** (6 passed).

- [ ] **Step 5: Commit:**
```bash
git add backend/app/services/ai/agenda_chair.py backend/tests/unit/test_agenda_chair.py
git commit -m "feat(chair): chair_curate_agenda (curaduría + reconstrucción anti-alucinación)"
```

---

### Task 2: Columna `chair_agenda` + migración

**Files:**
- Modify: `backend/app/models/annual_plan.py` (MonthlyPlan += `chair_agenda`)
- Create: `backend/scripts/add_chair_agenda_column.py`
- Test: `backend/tests/unit/test_chair_agenda_column.py`

- [ ] **Step 1: Write the failing test** at `backend/tests/unit/test_chair_agenda_column.py`:
```python
from app.models.annual_plan import MonthlyPlan


def test_monthlyplan_tiene_chair_agenda():
    m = MonthlyPlan(chair_agenda={"carta": "x", "items": []})
    assert m.chair_agenda == {"carta": "x", "items": []}


def test_chair_agenda_default_none():
    m = MonthlyPlan()
    assert m.chair_agenda is None
```

- [ ] **Step 2: Run it, verify it FAILS** (`TypeError: 'chair_agenda' is an invalid keyword argument`):
`cd backend && venv/bin/python -m pytest tests/unit/test_chair_agenda_column.py -v`

- [ ] **Step 3: Add the column.** In `backend/app/models/annual_plan.py`, in `MonthlyPlan`, right AFTER the `covered_themes` line, add:
```python
    chair_agenda: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
```

- [ ] **Step 4: Run the test, verify it PASSES** (2 passed). Also confirm the mappers still configure:
`cd backend && venv/bin/python -c "from app.models.annual_plan import MonthlyPlan; import sqlalchemy as sa; sa.orm.configure_mappers(); print('ok')"`

- [ ] **Step 5: Create the migration script** `backend/scripts/add_chair_agenda_column.py`:
```python
"""Agrega la columna monthly_plans.chair_agenda SIN Alembic (prod usa ALTER directo).
Idempotente (IF NOT EXISTS).

USO (solo cuando el humano lo autorice — toca la DB):
    venv/bin/python -m scripts.add_chair_agenda_column
"""
import asyncio

from sqlalchemy import text

from app.db.session import engine


async def main():
    async with engine.begin() as conn:
        await conn.execute(text(
            "ALTER TABLE monthly_plans ADD COLUMN IF NOT EXISTS chair_agenda JSONB"
        ))
    await engine.dispose()
    print("OK: columna monthly_plans.chair_agenda creada")


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 6: Commit:**
```bash
git add backend/app/models/annual_plan.py backend/scripts/add_chair_agenda_column.py backend/tests/unit/test_chair_agenda_column.py
git commit -m "feat(chair): columna chair_agenda en MonthlyPlan + migración"
```

---

### Task 3: `AgendaOut` + GET refactor + endpoint POST `/agenda/chair`

**Files:**
- Modify: `backend/app/schemas/agenda.py` (`AgendaOut`)
- Modify: `backend/app/api/v1/annual_plan/router.py`
- Test: `backend/tests/integration/test_agenda_api.py` (actualizar + nuevos)

- [ ] **Step 1: Update the test file** `backend/tests/integration/test_agenda_api.py` to its NEW content (the GET response changes shape to `AgendaOut`):
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


def _month(index, chair_agenda=None):
    m = MagicMock()
    m.id = uuid.uuid4(); m.month_index = index
    m.objectives = []; m.covered_themes = []
    m.status = "active"; m.review = None
    m.period_month = 12; m.period_year = 2026
    m.chair_agenda = chair_agenda
    return m


@pytest.mark.asyncio
async def test_get_agenda_determinista():
    plan = MagicMock(); plan.id = uuid.uuid4(); plan.user_id = MOCK_USER_ID
    plan.start_date = date(2020, 1, 1)  # mes activo = 12
    month = _month(1)  # no es el activo (activo=12) -> active_month None -> determinista
    themes = [_theme("fin", "permanente", 1, 0)]

    r1 = MagicMock(); r1.scalar_one_or_none.return_value = plan
    r2 = MagicMock(); r2.scalars.return_value.all.return_value = [month]
    r3 = MagicMock(); r3.scalars.return_value.all.return_value = themes
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
    assert body["curada"] is False
    assert isinstance(body["items"], list)
    assert any(i["detector"] == "TemaDeCobertura" for i in body["items"])
    assert body["items"][0]["orden"] == 1


@pytest.mark.asyncio
async def test_get_agenda_curada():
    plan = MagicMock(); plan.id = uuid.uuid4(); plan.user_id = MOCK_USER_ID
    plan.start_date = date(2020, 1, 1)  # mes activo = 12
    stored = {"carta": "Hola del Chair", "items": [
        {"orden": 1, "titulo": "X", "area": "kpi", "detector": "DesviaciónKPI",
         "impacto": "alto", "urgencia": "media", "racional": "r", "evidencia": ["e"], "score": 30.0}]}
    month = _month(12, chair_agenda=stored)  # ES el mes activo
    themes = [_theme("fin", "permanente", 1, 0)]

    r1 = MagicMock(); r1.scalar_one_or_none.return_value = plan
    r2 = MagicMock(); r2.scalars.return_value.all.return_value = [month]
    r3 = MagicMock(); r3.scalars.return_value.all.return_value = themes
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
    assert body["curada"] is True
    assert body["carta"] == "Hola del Chair"
    assert body["items"][0]["titulo"] == "X"


@pytest.mark.asyncio
async def test_post_chair_guarda_y_devuelve_curada(monkeypatch):
    def fake_chair(agenda, mb, period):
        return {"carta": "CARTA", "items": [
            {"orden": 1, "titulo": "C", "area": "kpi", "detector": "DesviaciónKPI",
             "impacto": "alto", "urgencia": "media", "racional": "prosa", "evidencia": ["e"], "score": 30.0}]}
    monkeypatch.setattr("app.api.v1.annual_plan.router.chair_curate_agenda", fake_chair)

    plan = MagicMock(); plan.id = uuid.uuid4(); plan.user_id = MOCK_USER_ID
    plan.start_date = date(2020, 1, 1)  # activo = 12
    month = _month(12)  # es el activo
    themes = [_theme("fin", "permanente", 1, 0)]
    onb = MagicMock(); onb.memory_buffer = {}

    r1 = MagicMock(); r1.scalar_one_or_none.return_value = plan          # _current_plan
    r2 = MagicMock(); r2.scalars.return_value.all.return_value = [month] # months
    r3 = MagicMock(); r3.scalars.return_value.all.return_value = themes  # themes
    r4 = MagicMock(); r4.scalar_one_or_none.return_value = onb           # onboarding
    db = AsyncMock(); db.execute = AsyncMock(side_effect=[r1, r2, r3, r4])

    app.dependency_overrides[get_db] = _db_override(db)
    app.dependency_overrides[get_current_user_id] = _user_override
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.post("/api/v1/annual-plan/agenda/chair")
    finally:
        app.dependency_overrides.clear()

    assert r.status_code == 200
    body = r.json()
    assert body["curada"] is True
    assert body["carta"] == "CARTA"
    assert body["items"][0]["titulo"] == "C"
    assert month.chair_agenda["carta"] == "CARTA"  # se persistió en el mes activo
```

- [ ] **Step 2: Run it, verify it FAILS** (GET aún devuelve lista / POST no existe):
`cd backend && venv/bin/python -m pytest tests/integration/test_agenda_api.py -v`

- [ ] **Step 3: Add `AgendaOut` to** `backend/app/schemas/agenda.py` (después de `AgendaItem`):
```python
class AgendaOut(BaseModel):
    curada: bool
    carta: str
    items: list[AgendaItem]
```

- [ ] **Step 4: Add imports** to `backend/app/api/v1/annual_plan/router.py` (con los otros imports):
```python
from app.schemas.agenda import AgendaItem, AgendaOut
from app.services.ai.agenda_chair import chair_curate_agenda
```
(Si `AgendaItem` ya estaba importado en su propia línea, cámbiala para incluir `AgendaOut`.)

- [ ] **Step 5: Add the shared helper** `_agenda_estado` directly ABOVE the existing `get_agenda` endpoint:
```python
async def _agenda_estado(plan, db: AsyncSession):
    """Reúne el EstadoMes en vivo y devuelve (agenda_determinista, months, active, active_month)."""
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
    active_month = next((m for m in months if m.month_index == active), None)
    return agenda, months, active, active_month
```

- [ ] **Step 6: Replace the existing `get_agenda` endpoint** so it returns `AgendaOut` (usa el helper y devuelve la curada si está guardada). Reemplaza el decorador+función actual por:
```python
@router.get("/annual-plan/agenda", response_model=AgendaOut)
async def get_agenda(
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    plan = await _current_plan(user_id, db)
    if not plan:
        raise HTTPException(status_code=404, detail="No hay plan generado.")
    agenda, _months, _active, active_month = await _agenda_estado(plan, db)
    if active_month is not None and active_month.chair_agenda:
        ca = active_month.chair_agenda
        return AgendaOut(curada=True, carta=ca.get("carta", ""), items=ca.get("items", []))
    return AgendaOut(curada=False, carta="", items=agenda)
```

- [ ] **Step 7: Add the POST endpoint** right after `get_agenda`:
```python
@router.post("/annual-plan/agenda/chair", response_model=AgendaOut)
async def convocar_chair(
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    plan = await _current_plan(user_id, db)
    if not plan:
        raise HTTPException(status_code=404, detail="No hay plan generado.")
    agenda, _months, _active, active_month = await _agenda_estado(plan, db)

    period_label = (
        f"{_MONTH_NAMES[active_month.period_month]} {active_month.period_year}"
        if active_month is not None else ""
    )
    memory_buffer: dict = {}
    try:
        onb = await db.execute(
            select(OnboardingSession).where(OnboardingSession.user_id == user_id)
            .order_by(OnboardingSession.created_at.desc()).limit(1)
        )
        onboarding = onb.scalar_one_or_none()
        memory_buffer = (onboarding.memory_buffer if onboarding else {}) or {}
    except Exception:
        memory_buffer = {}

    result = await anyio.to_thread.run_sync(chair_curate_agenda, agenda, memory_buffer, period_label)

    if active_month is not None:
        active_month.chair_agenda = {
            "carta": result["carta"], "items": result["items"],
            "generated_at": date.today().isoformat(),
        }
        _flag_modified(active_month, "chair_agenda")

    return AgendaOut(curada=True, carta=result["carta"], items=result["items"])
```

- [ ] **Step 8: Run the tests, verify they PASS:**
`cd backend && venv/bin/python -m pytest tests/integration/test_agenda_api.py -v` (3 passed)

- [ ] **Step 9: Run the full backend suite (no regressions):**
`cd backend && venv/bin/python -m pytest -q`

- [ ] **Step 10: Commit:**
```bash
git add backend/app/schemas/agenda.py backend/app/api/v1/annual_plan/router.py backend/tests/integration/test_agenda_api.py
git commit -m "feat(chair): AgendaOut + GET curada/determinista + POST /agenda/chair"
```

---

### Task 4: Frontend — botón Convocar al Chair + carta

**Files:**
- Modify: `frontend/src/lib/agenda.ts`
- Modify: `frontend/src/components/plan/AgendaPanel.tsx`

- [ ] **Step 1: Update the lib** `frontend/src/lib/agenda.ts` to its NEW content (la respuesta ahora es `AgendaOut`):
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

export interface AgendaOut {
  curada: boolean
  carta: string
  items: AgendaItem[]
}

export async function getAgenda(): Promise<AgendaOut> {
  const r = await api.get<AgendaOut>("/annual-plan/agenda")
  return r.data
}

export async function convocarChair(): Promise<AgendaOut> {
  const r = await api.post<AgendaOut>("/annual-plan/agenda/chair")
  return r.data
}
```

- [ ] **Step 2: Update the panel** `frontend/src/components/plan/AgendaPanel.tsx` to its NEW content:
```tsx
"use client"

import { useEffect, useState } from "react"
import { AgendaOut, getAgenda, convocarChair } from "@/lib/agenda"

const CHIP: Record<string, string> = {
  alto: "bg-red-100 text-red-700", alta: "bg-red-100 text-red-700",
  medio: "bg-amber-100 text-amber-700", media: "bg-amber-100 text-amber-700",
  bajo: "bg-gray-100 text-gray-500", baja: "bg-gray-100 text-gray-500",
}

export default function AgendaPanel() {
  const [data, setData] = useState<AgendaOut | null>(null)
  const [convocando, setConvocando] = useState(false)

  useEffect(() => {
    let active = true
    getAgenda().then(d => { if (active) setData(d) }).catch(() => { if (active) setData(null) })
    return () => { active = false }
  }, [])

  const onConvocar = async () => {
    setConvocando(true)
    try { setData(await convocarChair()) } catch { /* noop */ } finally { setConvocando(false) }
  }

  if (data === null) return null
  if (data.items.length === 0) {
    return (
      <div className="mb-4 rounded-2xl border border-gray-100 bg-white p-4">
        <h3 className="text-sm font-bold text-black uppercase tracking-wide mb-1">Agenda del mes</h3>
        <p className="text-sm text-gray-400">Sin temas priorizados este mes.</p>
      </div>
    )
  }

  return (
    <div className="mb-4 rounded-2xl border border-gray-100 bg-white p-4">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-bold text-black uppercase tracking-wide">Agenda del mes</h3>
        <button
          type="button"
          onClick={onConvocar}
          disabled={convocando}
          className="text-xs font-medium text-[var(--gob-navy)] hover:underline disabled:opacity-50"
        >
          {convocando ? "El Chair está revisando…" : (data.curada ? "Actualizar con el Chair" : "Convocar al Chair")}
        </button>
      </div>

      {data.curada && data.carta && (
        <p className="text-sm text-gray-600 italic border-l-2 border-[var(--gob-navy)] pl-3 mb-3">
          {data.carta}
        </p>
      )}

      <ol className="space-y-3">
        {data.items.map(i => (
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

- [ ] **Step 3: Typecheck, lint, build:**
```bash
cd frontend && npx tsc --noEmit && npx eslint src/lib/agenda.ts src/components/plan/AgendaPanel.tsx && npm run build
```
Expected: TSC OK, lint clean, `✓ Compiled successfully`.

- [ ] **Step 4: Commit:**
```bash
git add frontend/src/lib/agenda.ts frontend/src/components/plan/AgendaPanel.tsx
git commit -m "feat(chair): botón Convocar al Chair + carta en AgendaPanel"
```

---

## Done criteria

- Botón "Convocar al Chair" corre la IA, persiste en el mes activo, muestra carta + agenda curada.
- Sin API key / fallo → se mantiene la determinista (`curada=false`).
- Suite backend verde; `tsc` + build verdes.
- **Migración a prod**: correr `python -m scripts.add_chair_agenda_column` ANTES del deploy (aditiva; el código actual no lee `chair_agenda`).

## Notes for the implementer

- **El Chair es best-effort:** cualquier fallo (sin key, parseo inválido, excepción) → fallback determinista. NO debe romper el endpoint.
- **anti-alucinación:** `_rebuild` SOLO reordena y reescribe racional de los temas dados; conserva titulo/evidencia/score originales.
- **`GET /agenda` cambia de forma** (`list` → `AgendaOut`): por eso se actualiza `test_agenda_api.py` y la lib del frontend.
- **`anyio`, `_flag_modified`, `_MONTH_NAMES`, `OnboardingSession`** ya están importados en el router (de B4/B5/E); no los dupliques.
- **Migración aditiva**: correr el script en prod antes del deploy (igual que `covered_themes`).
