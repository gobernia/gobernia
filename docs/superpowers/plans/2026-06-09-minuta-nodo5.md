# Nodo 5 — Minuta (V1 single-pass) · Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Un botón "Sesionar el Consejo" que genera una Minuta (carta + 3-5 decisiones binarias) desde la agenda del mes; el dueño cierra cada decisión A/B/Aplazar y A/B generan un compromiso dentro de la Minuta.

**Architecture:** Servicio sync `generate_minuta` (molde de `agenda_chair`, best-effort + reconstrucción anti-alucinación). Columna `minuta` JSONB en `MonthlyPlan`. Endpoints `POST/GET /annual-plan/minuta` y `POST /annual-plan/minuta/decision`. Frontend: pestaña "Minuta" en el toggle del plan.

**Tech Stack:** FastAPI, SQLAlchemy async (JSONB), anthropic SDK, anyio.to_thread, pytest, Next.js 16 + TS.

**Spec:** `docs/superpowers/specs/2026-06-09-minuta-nodo5-design.md`

**Patrones existentes (verificados):**
- LLM: `_create_with_retry` + `_build_company_context` en `app/services/ai/agents/base.py`; `settings` desde `app.core.config`. Patrón best-effort idéntico a `app/services/ai/agenda_chair.py`.
- `MonthlyPlan` (`app/models/annual_plan.py`): `chair_agenda` JSONB en l.68 — añadir `minuta` después.
- Migración: patrón `scripts/add_chair_agenda_column.py`.
- Router `annual_plan/router.py`: tiene `_agenda_estado(plan, db) -> (agenda, months, active, active_month)`; importa `compute_active_month_index`, `_current_plan`, `MonthlyPlan`, `select`, `selectinload`, `_MONTH_NAMES`, `OnboardingSession`, `anyio`, `flag_modified as _flag_modified`, `date`, `datetime`. **NO importa `timedelta`** (se agrega).

---

### Task 1: Servicio `generate_minuta`

**Files:**
- Create: `backend/app/services/ai/minuta.py`
- Test: `backend/tests/unit/test_minuta_service.py`

- [ ] **Step 1: Write the failing test** at `backend/tests/unit/test_minuta_service.py`:
```python
from app.services.ai import minuta as minuta_mod
from app.services.ai.minuta import generate_minuta, _rebuild_minuta

AGENDA = [
    {"titulo": "KPI Margen fuera de objetivo", "evidencia": ["Margen: 8% (meta 15%)"], "racional": "rac kpi"},
    {"titulo": "Cubrir Auditoría", "evidencia": ["Auditoría: 0 de 4"], "racional": "rac aud"},
]


def test_fallback_sin_api_key(monkeypatch):
    monkeypatch.setattr(minuta_mod.settings, "ANTHROPIC_API_KEY", "")
    out = generate_minuta(AGENDA, {}, "Junio 2026")
    assert out["carta"] == ""
    assert len(out["temas"]) == 2
    t0 = out["temas"][0]
    assert t0["id"] == 0 and t0["titulo"] == "KPI Margen fuera de objetivo"
    assert t0["sintesis"] == "rac kpi"
    assert t0["decision"]["decision_tomada"] is None
    assert t0["decision"]["opcion_a"] and t0["decision"]["opcion_b"]
    assert t0["compromiso"] is None


def test_agenda_vacia(monkeypatch):
    monkeypatch.setattr(minuta_mod.settings, "ANTHROPIC_API_KEY", "sk-test")
    assert generate_minuta([], {}, "Junio 2026") == {"carta": "", "temas": []}


def test_cap_5(monkeypatch):
    monkeypatch.setattr(minuta_mod.settings, "ANTHROPIC_API_KEY", "")
    big = [{"titulo": f"T{i}", "evidencia": [], "racional": f"r{i}"} for i in range(8)]
    out = generate_minuta(big, {}, "X")
    assert len(out["temas"]) == 5
    assert [t["id"] for t in out["temas"]] == [0, 1, 2, 3, 4]


def test_rebuild_usa_llm_y_ancla_titulo():
    temas_llm = {"0": {"sintesis": "s0", "pregunta": "p0", "opcion_a": "a0", "opcion_b": "b0"}}
    out = _rebuild_minuta(AGENDA, temas_llm)
    assert out[0]["titulo"] == "KPI Margen fuera de objetivo"  # anclado a la agenda
    assert out[0]["sintesis"] == "s0"
    assert out[0]["decision"]["pregunta"] == "p0"
    assert out[0]["decision"]["opcion_a"] == "a0"
    assert out[1]["sintesis"] == "rac aud"  # sin llm para id 1 -> fallback al racional
    assert out[1]["decision"]["opcion_a"]  # decisión genérica presente
```

- [ ] **Step 2: Run it, verify it FAILS** (`ModuleNotFoundError`):
`cd backend && venv/bin/python -m pytest tests/unit/test_minuta_service.py -v`

- [ ] **Step 3: Implement** `backend/app/services/ai/minuta.py`:
```python
"""Genera la Minuta del consejo (nodo 5, V1 single-pass). Best-effort con fallback determinista.

Reconstrucción anti-alucinación: los temas se anclan a la agenda dada (titulo); el Chair solo
añade síntesis + decisión binaria. Nunca inventa temas.
"""
import json

import anthropic

from app.core.config import settings
from app.services.ai.agents.base import _build_company_context, _create_with_retry

_MAX_TEMAS = 5
_DEF_PREGUNTA = "¿Cómo proceder con: {titulo}?"
_DEF_A = "Tomar acción este mes."
_DEF_B = "Aplazar y monitorear."

_MINUTA_SYSTEM = (
    "Eres el Chair (presidente) de un consejo de administración de una empresa familiar, "
    "presidiendo la sesión mensual. Recibes la agenda priorizada del mes. Por cada tema:\n"
    "1) Escribe una 'sintesis' breve (1-2 frases) de la deliberación del consejo sobre el tema.\n"
    "2) Plantea una 'decision' binaria que el dueño debe cerrar: una 'pregunta' clara y dos "
    "opciones concretas y accionables ('opcion_a' y 'opcion_b'), cada una una acción específica.\n"
    "Además escribe una 'carta' de apertura de máximo 120 palabras, sobria y directiva.\n"
    "NO inventes temas nuevos: trabaja SOLO con los temas dados (por su id). "
    "Responde ÚNICAMENTE con JSON válido."
)


def generate_minuta(agenda_items: list[dict], memory_buffer: dict, period_label: str) -> dict:
    items = (agenda_items or [])[:_MAX_TEMAS]
    if not items:
        return {"carta": "", "temas": []}
    if not settings.ANTHROPIC_API_KEY:
        return {"carta": "", "temas": _rebuild_minuta(items, {})}

    company_ctx = _build_company_context(memory_buffer or {})
    items_for_llm = [
        {"id": i, "titulo": it["titulo"], "evidencia": it.get("evidencia", []),
         "racional": it.get("racional", "")}
        for i, it in enumerate(items)
    ]
    user_prompt = (
        f"EMPRESA:\n{company_ctx}\n\n"
        f"MES: {period_label}\n\n"
        f"AGENDA DEL MES:\n{json.dumps(items_for_llm, ensure_ascii=False, indent=2)}\n\n"
        "Sesiona el consejo. Responde ÚNICAMENTE con JSON con esta forma exacta:\n"
        '{"carta": "<=120 palabras", "temas": {"<id>": '
        '{"sintesis": "...", "pregunta": "...", "opcion_a": "...", "opcion_b": "..."}}}'
    )
    try:
        client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
        response = _create_with_retry(
            client, model=settings.AI_MODEL, max_tokens=2048,
            system=_MINUTA_SYSTEM,
            messages=[{"role": "user", "content": user_prompt}],
        )
        parsed = json.loads(_extract_json(response.content[0].text))
        carta = str(parsed.get("carta") or "")
        temas_llm = parsed.get("temas") or {}
        return {"carta": carta, "temas": _rebuild_minuta(items, temas_llm)}
    except Exception:
        return {"carta": "", "temas": _rebuild_minuta(items, {})}


def _extract_json(text: str) -> str:
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise ValueError("respuesta sin JSON")
    return text[start:end + 1]


def _rebuild_minuta(items: list[dict], temas_llm: dict) -> list[dict]:
    temas: list[dict] = []
    for i, it in enumerate(items):
        llm = temas_llm.get(str(i)) or {}
        titulo = it["titulo"]
        temas.append({
            "id": i,
            "titulo": titulo,
            "sintesis": str(llm.get("sintesis") or it.get("racional") or ""),
            "decision": {
                "pregunta": str(llm.get("pregunta") or _DEF_PREGUNTA.format(titulo=titulo)),
                "opcion_a": str(llm.get("opcion_a") or _DEF_A),
                "opcion_b": str(llm.get("opcion_b") or _DEF_B),
                "decision_tomada": None,
            },
            "compromiso": None,
        })
    return temas
```
(Confirma que el import de `settings` coincide con `app/services/ai/minuta.py` vecinos — `from app.core.config import settings`.)

- [ ] **Step 4: Run the test, verify it PASSES** (4 passed).

- [ ] **Step 5: Commit:**
```bash
git add backend/app/services/ai/minuta.py backend/tests/unit/test_minuta_service.py
git commit -m "feat(minuta): generate_minuta (Chair single-pass + reconstrucción anti-alucinación)"
```

---

### Task 2: Columna `minuta` + migración

**Files:**
- Modify: `backend/app/models/annual_plan.py` (MonthlyPlan += `minuta`)
- Create: `backend/scripts/add_minuta_column.py`
- Test: `backend/tests/unit/test_minuta_column.py`

- [ ] **Step 1: Write the failing test** at `backend/tests/unit/test_minuta_column.py`:
```python
from app.models.annual_plan import MonthlyPlan


def test_monthlyplan_tiene_minuta():
    m = MonthlyPlan(minuta={"carta": "x", "temas": []})
    assert m.minuta == {"carta": "x", "temas": []}


def test_minuta_default_none():
    m = MonthlyPlan()
    assert m.minuta is None
```

- [ ] **Step 2: Run it, verify it FAILS** (`TypeError: 'minuta' is an invalid keyword argument`):
`cd backend && venv/bin/python -m pytest tests/unit/test_minuta_column.py -v`

- [ ] **Step 3: Add the column.** In `backend/app/models/annual_plan.py`, in `MonthlyPlan`, immediately AFTER the `chair_agenda` line, add:
```python
    minuta: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
```

- [ ] **Step 4: Run the test, verify it PASSES** (2 passed). Confirm mappers configure:
`cd backend && venv/bin/python -c "from app.models.annual_plan import MonthlyPlan; import sqlalchemy as sa; sa.orm.configure_mappers(); print('ok')"`

- [ ] **Step 5: Create the migration script** `backend/scripts/add_minuta_column.py`:
```python
"""Agrega la columna monthly_plans.minuta SIN Alembic (prod usa ALTER directo).
Idempotente (IF NOT EXISTS).

USO (solo cuando el humano lo autorice — toca la DB):
    venv/bin/python -m scripts.add_minuta_column
"""
import asyncio

from sqlalchemy import text

from app.db.session import engine


async def main():
    async with engine.begin() as conn:
        await conn.execute(text(
            "ALTER TABLE monthly_plans ADD COLUMN IF NOT EXISTS minuta JSONB"
        ))
    await engine.dispose()
    print("OK: columna monthly_plans.minuta creada")


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 6: Commit** (NO ejecutes el script — toca prod, lo corre el controlador):
```bash
git add backend/app/models/annual_plan.py backend/scripts/add_minuta_column.py backend/tests/unit/test_minuta_column.py
git commit -m "feat(minuta): columna minuta en MonthlyPlan + migración"
```

---

### Task 3: Esquemas + endpoints (POST/GET/decision)

**Files:**
- Create: `backend/app/schemas/minuta.py`
- Modify: `backend/app/api/v1/annual_plan/router.py`
- Test: `backend/tests/integration/test_minuta_api.py`

- [ ] **Step 1: Write the failing test** at `backend/tests/integration/test_minuta_api.py`:
```python
import uuid
from datetime import date
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.models.board_theme import BoardTheme
from app.core.dependencies import get_current_user_id, get_db

MOCK_USER_ID = "user_test_minuta"


def _theme(key, type_, freq, order):
    return BoardTheme(key=key, label=key.title(), type=type_,
                      every_n_sessions=freq, active=True, order_index=order)


def _db_override(db):
    async def override():
        yield db
    return override


async def _user_override():
    return MOCK_USER_ID


def _tema(tid=0):
    return {"id": tid, "titulo": "Tema", "sintesis": "s",
            "decision": {"pregunta": "p", "opcion_a": "Acción A", "opcion_b": "Acción B",
                         "decision_tomada": None},
            "compromiso": None}


def _month(index, minuta=None, chair_agenda=None):
    m = MagicMock()
    m.id = uuid.uuid4(); m.month_index = index
    m.objectives = []; m.covered_themes = []
    m.status = "active"; m.review = None
    m.period_month = 12; m.period_year = 2026
    m.chair_agenda = chair_agenda; m.minuta = minuta
    return m


def _setup(db):
    app.dependency_overrides[get_db] = _db_override(db)
    app.dependency_overrides[get_current_user_id] = _user_override


@pytest.mark.asyncio
async def test_post_minuta_genera_y_guarda(monkeypatch):
    monkeypatch.setattr("app.api.v1.annual_plan.router.generate_minuta",
                        lambda items, mb, period: {"carta": "MINUTA", "temas": [_tema()]})
    plan = MagicMock(); plan.id = uuid.uuid4(); plan.user_id = MOCK_USER_ID
    plan.start_date = date(2020, 1, 1)  # activo = 12
    month = _month(12)
    themes = [_theme("fin", "permanente", 1, 0)]
    onb = MagicMock(); onb.memory_buffer = {}

    r1 = MagicMock(); r1.scalar_one_or_none.return_value = plan
    r2 = MagicMock(); r2.scalars.return_value.all.return_value = [month]
    r3 = MagicMock(); r3.scalars.return_value.all.return_value = themes
    r4 = MagicMock(); r4.scalar_one_or_none.return_value = onb
    db = AsyncMock(); db.execute = AsyncMock(side_effect=[r1, r2, r3, r4])

    _setup(db)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.post("/api/v1/annual-plan/minuta")
    finally:
        app.dependency_overrides.clear()

    assert r.status_code == 200
    body = r.json()
    assert body["generada"] is True
    assert body["carta"] == "MINUTA"
    assert month.minuta["carta"] == "MINUTA"


@pytest.mark.asyncio
async def test_get_minuta_vacia():
    plan = MagicMock(); plan.id = uuid.uuid4(); plan.user_id = MOCK_USER_ID
    plan.start_date = date(2020, 1, 1)
    month = _month(12, minuta=None)
    r1 = MagicMock(); r1.scalar_one_or_none.return_value = plan
    r2 = MagicMock(); r2.scalars.return_value.all.return_value = [month]
    db = AsyncMock(); db.execute = AsyncMock(side_effect=[r1, r2])

    _setup(db)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.get("/api/v1/annual-plan/minuta")
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 200
    assert r.json()["generada"] is False


@pytest.mark.asyncio
async def test_decision_A_genera_compromiso():
    plan = MagicMock(); plan.id = uuid.uuid4(); plan.user_id = MOCK_USER_ID
    plan.start_date = date(2020, 1, 1)
    month = _month(12, minuta={"carta": "C", "temas": [_tema(0)]})
    r1 = MagicMock(); r1.scalar_one_or_none.return_value = plan
    r2 = MagicMock(); r2.scalars.return_value.all.return_value = [month]
    db = AsyncMock(); db.execute = AsyncMock(side_effect=[r1, r2])

    _setup(db)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.post("/api/v1/annual-plan/minuta/decision",
                             json={"tema_id": 0, "decision": "A"})
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 200
    body = r.json()
    assert body["temas"][0]["decision"]["decision_tomada"] == "A"
    assert body["temas"][0]["compromiso"]["descripcion"] == "Acción A"


@pytest.mark.asyncio
async def test_decision_aplazar_sin_compromiso():
    plan = MagicMock(); plan.id = uuid.uuid4(); plan.user_id = MOCK_USER_ID
    plan.start_date = date(2020, 1, 1)
    month = _month(12, minuta={"carta": "C", "temas": [_tema(0)]})
    r1 = MagicMock(); r1.scalar_one_or_none.return_value = plan
    r2 = MagicMock(); r2.scalars.return_value.all.return_value = [month]
    db = AsyncMock(); db.execute = AsyncMock(side_effect=[r1, r2])

    _setup(db)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.post("/api/v1/annual-plan/minuta/decision",
                             json={"tema_id": 0, "decision": "aplazar"})
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 200
    body = r.json()
    assert body["temas"][0]["decision"]["decision_tomada"] == "aplazar"
    assert body["temas"][0]["compromiso"] is None


@pytest.mark.asyncio
async def test_decision_invalida_422():
    plan = MagicMock(); plan.id = uuid.uuid4(); plan.user_id = MOCK_USER_ID
    plan.start_date = date(2020, 1, 1)
    month = _month(12, minuta={"carta": "C", "temas": [_tema(0)]})
    r1 = MagicMock(); r1.scalar_one_or_none.return_value = plan
    r2 = MagicMock(); r2.scalars.return_value.all.return_value = [month]
    db = AsyncMock(); db.execute = AsyncMock(side_effect=[r1, r2])

    _setup(db)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.post("/api/v1/annual-plan/minuta/decision",
                             json={"tema_id": 0, "decision": "C"})
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 422
```

- [ ] **Step 2: Run it, verify it FAILS** (schema/endpoints no existen):
`cd backend && venv/bin/python -m pytest tests/integration/test_minuta_api.py -v`

- [ ] **Step 3: Create the schema** `backend/app/schemas/minuta.py`:
```python
from pydantic import BaseModel


class MinutaDecision(BaseModel):
    pregunta: str
    opcion_a: str
    opcion_b: str
    decision_tomada: str | None = None


class MinutaCompromiso(BaseModel):
    descripcion: str
    fecha: str


class MinutaTema(BaseModel):
    id: int
    titulo: str
    sintesis: str
    decision: MinutaDecision
    compromiso: MinutaCompromiso | None = None


class MinutaOut(BaseModel):
    generada: bool
    carta: str
    temas: list[MinutaTema]


class DecisionIn(BaseModel):
    tema_id: int
    decision: str
```

- [ ] **Step 4: Add imports + `timedelta`** to `backend/app/api/v1/annual_plan/router.py`:
  - Change `from datetime import date, datetime` → `from datetime import date, datetime, timedelta`.
  - Add:
```python
from app.schemas.minuta import MinutaOut, DecisionIn
from app.services.ai.minuta import generate_minuta
```

- [ ] **Step 5: Add the light helper** `_active_month` (cerca de `_agenda_estado`):
```python
async def _active_month(plan, db: AsyncSession):
    """Devuelve el MonthlyPlan del mes activo (sin construir la agenda)."""
    res = await db.execute(select(MonthlyPlan).where(MonthlyPlan.annual_plan_id == plan.id))
    months = list(res.scalars().all())
    active = compute_active_month_index(plan.start_date, date.today())
    return next((m for m in months if m.month_index == active), None)
```

- [ ] **Step 6: Add the three endpoints at the END of the router file:**
```python
# ── Minuta (nodo 5) ───────────────────────────────────────────────────────────

@router.post("/annual-plan/minuta", response_model=MinutaOut)
async def generar_minuta(
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    plan = await _current_plan(user_id, db)
    if not plan:
        raise HTTPException(status_code=404, detail="No hay plan generado.")
    agenda, _months, _active, active_month = await _agenda_estado(plan, db)
    items = (
        active_month.chair_agenda["items"]
        if (active_month is not None and active_month.chair_agenda) else agenda
    )
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

    result = await anyio.to_thread.run_sync(generate_minuta, items, memory_buffer, period_label)

    if active_month is not None:
        active_month.minuta = {
            "carta": result["carta"], "temas": result["temas"],
            "generated_at": date.today().isoformat(),
        }
        _flag_modified(active_month, "minuta")

    return MinutaOut(generada=True, carta=result["carta"], temas=result["temas"])


@router.get("/annual-plan/minuta", response_model=MinutaOut)
async def get_minuta(
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    plan = await _current_plan(user_id, db)
    if not plan:
        raise HTTPException(status_code=404, detail="No hay plan generado.")
    active_month = await _active_month(plan, db)
    if active_month is not None and active_month.minuta:
        m = active_month.minuta
        return MinutaOut(generada=True, carta=m.get("carta", ""), temas=m.get("temas", []))
    return MinutaOut(generada=False, carta="", temas=[])


@router.post("/annual-plan/minuta/decision", response_model=MinutaOut)
async def cerrar_decision(
    body: DecisionIn,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    if body.decision not in ("A", "B", "aplazar"):
        raise HTTPException(status_code=422, detail="Decisión inválida.")
    plan = await _current_plan(user_id, db)
    if not plan:
        raise HTTPException(status_code=404, detail="No hay plan generado.")
    active_month = await _active_month(plan, db)
    if active_month is None or not active_month.minuta:
        raise HTTPException(status_code=404, detail="Minuta no encontrada.")

    minuta = dict(active_month.minuta)
    temas = minuta.get("temas", [])
    tema = next((t for t in temas if t.get("id") == body.tema_id), None)
    if tema is None:
        raise HTTPException(status_code=404, detail="Tema no encontrado.")

    tema["decision"]["decision_tomada"] = body.decision
    if body.decision in ("A", "B"):
        opcion = tema["decision"]["opcion_a"] if body.decision == "A" else tema["decision"]["opcion_b"]
        tema["compromiso"] = {
            "descripcion": opcion,
            "fecha": (date.today() + timedelta(days=14)).isoformat(),
        }
    else:
        tema["compromiso"] = None

    active_month.minuta = minuta
    _flag_modified(active_month, "minuta")
    return MinutaOut(generada=True, carta=minuta.get("carta", ""), temas=temas)
```
Nota: `DecisionIn.decision` se valida con un `if ... not in {...}` (422) en vez de un Enum, para devolver 422 explícito.

- [ ] **Step 7: Run the tests, verify they PASS** (5 passed):
`cd backend && venv/bin/python -m pytest tests/integration/test_minuta_api.py -v`

- [ ] **Step 8: Run the full backend suite (no regressions):**
`cd backend && venv/bin/python -m pytest -q`

- [ ] **Step 9: Commit:**
```bash
git add backend/app/schemas/minuta.py backend/app/api/v1/annual_plan/router.py backend/tests/integration/test_minuta_api.py
git commit -m "feat(minuta): esquemas + endpoints POST/GET /minuta + decision"
```

---

### Task 4: Frontend — pestaña Minuta

**Files:**
- Create: `frontend/src/lib/minuta.ts`
- Create: `frontend/src/components/plan/MinutaView.tsx`
- Modify: `frontend/src/app/dashboard/plan/page.tsx` (toggle += "minuta")

- [ ] **Step 1: Create the lib** `frontend/src/lib/minuta.ts`:
```typescript
import api from "@/lib/api"

export interface MinutaDecision {
  pregunta: string
  opcion_a: string
  opcion_b: string
  decision_tomada: string | null
}

export interface MinutaCompromiso {
  descripcion: string
  fecha: string
}

export interface MinutaTema {
  id: number
  titulo: string
  sintesis: string
  decision: MinutaDecision
  compromiso: MinutaCompromiso | null
}

export interface MinutaOut {
  generada: boolean
  carta: string
  temas: MinutaTema[]
}

export async function getMinuta(): Promise<MinutaOut> {
  const r = await api.get<MinutaOut>("/annual-plan/minuta")
  return r.data
}

export async function sesionarConsejo(): Promise<MinutaOut> {
  const r = await api.post<MinutaOut>("/annual-plan/minuta")
  return r.data
}

export async function cerrarDecision(temaId: number, decision: "A" | "B" | "aplazar"): Promise<MinutaOut> {
  const r = await api.post<MinutaOut>("/annual-plan/minuta/decision", { tema_id: temaId, decision })
  return r.data
}
```

- [ ] **Step 2: Create the view** `frontend/src/components/plan/MinutaView.tsx`:
```tsx
"use client"

import { useEffect, useState } from "react"
import { MinutaOut, MinutaTema, getMinuta, sesionarConsejo, cerrarDecision } from "@/lib/minuta"

export default function MinutaView() {
  const [data, setData] = useState<MinutaOut | null>(null)
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    let active = true
    getMinuta().then(d => { if (active) setData(d) }).catch(() => { if (active) setData(null) })
    return () => { active = false }
  }, [])

  const onSesionar = async () => {
    setBusy(true)
    try { setData(await sesionarConsejo()) } catch { /* noop */ } finally { setBusy(false) }
  }

  const onDecidir = async (temaId: number, decision: "A" | "B" | "aplazar") => {
    setBusy(true)
    try { setData(await cerrarDecision(temaId, decision)) } catch { /* noop */ } finally { setBusy(false) }
  }

  if (data === null) return <p className="text-sm text-gray-400">Cargando minuta…</p>

  if (!data.generada) {
    return (
      <div className="rounded-2xl border border-gray-100 bg-white p-6 text-center">
        <p className="text-sm text-gray-500 mb-4">Aún no has sesionado al consejo este mes.</p>
        <button
          type="button"
          onClick={onSesionar}
          disabled={busy}
          className="px-4 py-2 rounded-lg bg-[var(--gob-navy)] text-[var(--gob-bone)] text-sm font-medium disabled:opacity-50"
        >
          {busy ? "El consejo está sesionando…" : "Sesionar el Consejo"}
        </button>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      {data.carta && (
        <p className="text-sm text-gray-600 italic border-l-2 border-[var(--gob-navy)] pl-3">{data.carta}</p>
      )}
      {data.temas.map(t => <TemaCard key={t.id} tema={t} busy={busy} onDecidir={onDecidir} />)}
      <button
        type="button"
        onClick={onSesionar}
        disabled={busy}
        className="text-xs font-medium text-[var(--gob-navy)] hover:underline disabled:opacity-50"
      >
        {busy ? "Sesionando…" : "Volver a sesionar"}
      </button>
    </div>
  )
}

function TemaCard({ tema, busy, onDecidir }: {
  tema: MinutaTema
  busy: boolean
  onDecidir: (id: number, d: "A" | "B" | "aplazar") => void
}) {
  const tomada = tema.decision.decision_tomada
  return (
    <div className="rounded-2xl border border-gray-100 bg-white p-4">
      <h4 className="text-sm font-bold text-black">{tema.titulo}</h4>
      <p className="text-xs text-gray-500 mt-1">{tema.sintesis}</p>
      <p className="text-sm text-black font-medium mt-3">{tema.decision.pregunta}</p>

      {tomada ? (
        <div className="mt-2 text-xs">
          <p className="text-gray-700">
            Decisión: <span className="font-medium">
              {tomada === "A" ? tema.decision.opcion_a : tomada === "B" ? tema.decision.opcion_b : "Aplazado"}
            </span>
          </p>
          {tema.compromiso && (
            <p className="text-gray-500 mt-1">
              Compromiso: {tema.compromiso.descripcion} · vence {tema.compromiso.fecha}
            </p>
          )}
        </div>
      ) : (
        <div className="flex flex-wrap gap-2 mt-3">
          <button type="button" disabled={busy} onClick={() => onDecidir(tema.id, "A")}
            className="px-3 py-1.5 rounded-lg border border-gray-200 text-xs hover:bg-gray-50 disabled:opacity-50">
            A · {tema.decision.opcion_a}
          </button>
          <button type="button" disabled={busy} onClick={() => onDecidir(tema.id, "B")}
            className="px-3 py-1.5 rounded-lg border border-gray-200 text-xs hover:bg-gray-50 disabled:opacity-50">
            B · {tema.decision.opcion_b}
          </button>
          <button type="button" disabled={busy} onClick={() => onDecidir(tema.id, "aplazar")}
            className="px-3 py-1.5 rounded-lg text-xs text-gray-400 hover:underline disabled:opacity-50">
            Aplazar
          </button>
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 3: Add the "Minuta" tab.** Read `frontend/src/app/dashboard/plan/page.tsx`. Changes:
  1. Import: `import MinutaView from "@/components/plan/MinutaView"`.
  2. Widen `boardView` type to include `"minuta"`: `useState<"meses" | "tablero" | "cobertura" | "minuta">("meses")`.
  3. Add `"minuta"` to the toggle array: `(["meses", "tablero", "cobertura", "minuta"] as const)`, and extend the label expression so `v === "minuta"` → `"Minuta"`.
  4. In the ternary that renders the views, add a `minuta` branch: `boardView === "minuta" ? (<MinutaView />) : ...`. Read the file to place it correctly alongside the existing `cobertura`/`tablero`/meses branches, keeping those unchanged.

- [ ] **Step 4: Typecheck, lint, build:**
```bash
cd frontend && npx tsc --noEmit && npx eslint src/lib/minuta.ts src/components/plan/MinutaView.tsx && npm run build
```
Expected: TSC OK, lint clean, `✓ Compiled successfully`. Fix only errors in new code.

- [ ] **Step 5: Commit:**
```bash
git add frontend/src/lib/minuta.ts frontend/src/components/plan/MinutaView.tsx frontend/src/app/dashboard/plan/page.tsx
git commit -m "feat(minuta): pestaña Minuta (sesionar + decisiones A/B/Aplazar)"
```

---

## Done criteria

- "Sesionar el Consejo" genera la Minuta (carta + 3-5 temas con decisión), persistida en el mes activo.
- Cerrar A/B genera un compromiso visible en el tema; Aplazar lo marca sin compromiso.
- Sin API key / fallo → minuta determinista (no rompe).
- Suite backend verde; `tsc` + build verdes.
- **Migración a prod**: correr `python -m scripts.add_minuta_column` ANTES del deploy.

## Notes for the implementer

- **Best-effort:** cualquier fallo del LLM → fallback determinista (no rompe el endpoint).
- **Anti-alucinación:** `_rebuild_minuta` ancla cada tema al titulo de la agenda; el LLM solo añade síntesis + decisión.
- **`generate_minuta` se llama vía `anyio.to_thread.run_sync`** (no bloquea el event loop).
- **`DecisionIn.decision`** se valida con `if not in {...}` → 422 (antes de tocar DB).
- **Migración aditiva**: correr el script en prod antes del deploy (igual que `chair_agenda`).
- `anyio`, `_flag_modified`, `_MONTH_NAMES`, `OnboardingSession`, `_agenda_estado` ya están en el router; solo falta `timedelta` (agregado al import de datetime).
