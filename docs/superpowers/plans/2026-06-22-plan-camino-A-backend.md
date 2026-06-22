# Plan Camino — Plan A: backend (explicación de tareas + generación informada por FODA) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** El backend para el nuevo plan: tareas con **explicación generada bajo demanda y cacheada** (qué es / cómo / tiempo / dificultad), y la **generación del plan informada por el FODA + metas** priorizadas.

**Architecture:** Columna `ActionTask.explicacion` (JSONB) + endpoint `POST /tasks/{id}/explicacion` que genera con Sonnet la primera vez y cachea. La generación del plan (Fase 3A) se enriquece inyectando un resumen del FODA + metas en `memory_buffer.ai_context.company_narrative`, que los generadores ya leen — sin tocar sus firmas. La UI (Camino + Timeline) es el Plan B.

**Tech Stack:** FastAPI, SQLAlchemy async, anthropic (Sonnet 4.6 = `settings.AI_MODEL`, tool use). Columna nueva vía `scripts/alter_*` (NO Alembic).

## Global Constraints

- **Bajo demanda + cache:** la explicación se genera al primer `POST` y se guarda en `ActionTask.explicacion`; el 2º `POST` devuelve la cacheada.
- **FODA al generador sin tocar firmas:** se enriquece `memory_buffer["ai_context"]["company_narrative"]`; los generadores existentes lo recogen vía `_build_company_context`.
- **Esquema:** `action_tasks` gana `explicacion JSONB` vía `scripts/alter_task_explicacion.py` (`ADD COLUMN IF NOT EXISTS`), corrido en prod con autorización.
- **Sin tocar el motor de generación** (Fase 3A) salvo el insumo del FODA.

---

### Task 1: Tareas explicadas (columna + generador + endpoint cacheado)

**Files:**
- Modify: `backend/app/models/action_plan.py` (`ActionTask.explicacion`)
- Create: `backend/scripts/alter_task_explicacion.py`
- Create: `backend/app/services/ai/task_explainer.py`
- Modify: `backend/app/api/v1/action_plans/router.py` (endpoint)
- Modify: `backend/app/schemas/action_plan.py` (`ActionTaskOut.explicacion`)
- Test: `backend/tests/unit/test_task_explainer.py`, `backend/tests/integration/test_task_explicacion_api.py`

**Interfaces:**
- Produces: `task_explainer.parse_explicacion(d: dict) -> dict`, `task_explainer.generate_explicacion(task_title, objetivo, empresa, kpi) -> dict`; `POST /tasks/{task_id}/explicacion` → `{tiempo, dificultad, que_es, como}`.

- [ ] **Step 1: Test del generador (lógica pura)**

`backend/tests/unit/test_task_explainer.py`:
```python
from app.services.ai.task_explainer import parse_explicacion


def test_parse_explicacion_normaliza():
    d = parse_explicacion({"tiempo": "~2 h", "dificultad": "Fácil",
                           "que_es": "Definir el cliente ideal",
                           "como": ["Lista tus mejores clientes", "Busca qué tienen en común"]})
    assert d["tiempo"] == "~2 h"
    assert d["dificultad"] == "Fácil"
    assert d["que_es"].startswith("Definir")
    assert d["como"] == ["Lista tus mejores clientes", "Busca qué tienen en común"]


def test_parse_explicacion_defaults_seguros():
    d = parse_explicacion({})
    assert d["tiempo"] and d["dificultad"] in ("Fácil", "Media", "Difícil")
    assert isinstance(d["que_es"], str)
    assert isinstance(d["como"], list)


def test_parse_explicacion_dificultad_invalida_cae_a_media():
    d = parse_explicacion({"dificultad": "imposible"})
    assert d["dificultad"] == "Media"
```

- [ ] **Step 2: Correr (falla)**

Run: `cd backend && ./venv/bin/pytest tests/unit/test_task_explainer.py -q`

- [ ] **Step 3: `task_explainer.py`**

`backend/app/services/ai/task_explainer.py`:
```python
"""Explicación de una tarea, generada bajo demanda (qué es / cómo / tiempo / dificultad)."""
import anthropic

from app.core.config import settings
from app.services.ai.agents.base import _create_with_retry

_DIFS = ("Fácil", "Media", "Difícil")

EXPLICACION_TOOL = {
    "name": "explicar_tarea",
    "description": "Explica una tarea del plan para que el dueño la entienda y la ejecute.",
    "input_schema": {
        "type": "object",
        "properties": {
            "tiempo": {"type": "string", "description": "Estimado, p. ej. '~2 h', '1 día'."},
            "dificultad": {"type": "string", "enum": list(_DIFS)},
            "que_es": {"type": "string", "description": "Qué es la tarea, claro y sin tecnicismos."},
            "como": {"type": "array", "items": {"type": "string"}, "description": "Pasos concretos."},
        },
        "required": ["tiempo", "dificultad", "que_es", "como"],
    },
}


def parse_explicacion(d: dict) -> dict:
    d = d or {}
    dif = d.get("dificultad") if d.get("dificultad") in _DIFS else "Media"
    como = d.get("como")
    como = [str(x) for x in como if str(x).strip()] if isinstance(como, list) else []
    return {
        "tiempo": str(d.get("tiempo") or "~1 h"),
        "dificultad": dif,
        "que_es": str(d.get("que_es") or ""),
        "como": como,
    }


def generate_explicacion(task_title: str, objetivo: str, empresa: str, kpi: str | None) -> dict:
    """Genera la explicación con Sonnet (tool use). Sin API key → explicación mínima."""
    if not settings.ANTHROPIC_API_KEY:
        return parse_explicacion({"que_es": task_title, "como": []})
    system = (
        "Eres Todd, secretario del consejo de Gobernia. Explica UNA tarea del plan al dueño de una "
        "empresa para que la entienda y la ejecute, en español, claro y sin tecnicismos. 'que_es': 2-4 "
        "oraciones de qué es y por qué importa. 'como': 3-5 pasos concretos y accionables. 'tiempo' y "
        "'dificultad' realistas. No inventes datos específicos que no tengas."
    )
    user = (
        f"EMPRESA: {empresa or 'N/D'}\n"
        f"OBJETIVO DEL MES: {objetivo or 'N/D'}\n"
        f"KPI relacionado: {kpi or 'N/D'}\n"
        f"TAREA: {task_title}"
    )
    try:
        client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY, timeout=120.0)
        response = _create_with_retry(
            client, model=settings.AI_MODEL, max_tokens=1024, system=system,
            messages=[{"role": "user", "content": user}],
            tools=[EXPLICACION_TOOL], tool_choice={"type": "tool", "name": "explicar_tarea"},
        )
        block = next((b for b in response.content if getattr(b, "type", None) == "tool_use"), None)
        return parse_explicacion(dict(block.input) if block and isinstance(block.input, dict) else {})
    except Exception:
        return parse_explicacion({"que_es": task_title, "como": []})
```

- [ ] **Step 4: Modelo + alter + schema**

En `backend/app/models/action_plan.py`, agregar a `ActionTask` (después de `required_doc`):
```python
    explicacion: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
```
(JSONB ya se importa en ese archivo — confirmar.)

`backend/scripts/alter_task_explicacion.py`:
```python
"""Agrega action_tasks.explicacion SIN Alembic. Idempotente.
USO (solo con autorización — toca la DB): venv/bin/python -m scripts.alter_task_explicacion"""
import asyncio
from sqlalchemy import text
from app.db.session import engine
import app.models  # noqa: F401
from app.models import Base


async def main():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.execute(text("ALTER TABLE action_tasks ADD COLUMN IF NOT EXISTS explicacion JSONB"))
    await engine.dispose()
    print("OK: columna explicacion agregada a action_tasks")


if __name__ == "__main__":
    asyncio.run(main())
```

En `backend/app/schemas/action_plan.py`, agregar a `ActionTaskOut`:
```python
    explicacion: dict | None = None
```
(Y en `_task_to_out` en el router, incluir `explicacion=t.explicacion` si la función construye el out campo por campo — READ y ajusta.)

- [ ] **Step 5: Test del endpoint**

`backend/tests/integration/test_task_explicacion_api.py`:
```python
import uuid
from unittest.mock import AsyncMock, MagicMock
import pytest
from httpx import ASGITransport, AsyncClient
from app.main import app
from app.core.dependencies import get_current_user_id, get_db

UID = "user_test_exp"


def _dbov(db):
    async def o():
        yield db
    return o


async def _uov():
    return UID


@pytest.mark.asyncio
async def test_explicacion_cacheada_no_regenera(monkeypatch):
    task = MagicMock()
    task.id = uuid.uuid4(); task.title = "Lanzar campaña"; task.objective_id = None
    task.kpi_ref = None; task.explicacion = {"tiempo": "~2 h", "dificultad": "Media",
                                             "que_es": "ya", "como": ["a"]}

    async def fake_owned(tid, uid, db):
        return task
    monkeypatch.setattr("app.api.v1.action_plans.router._get_user_task_or_404", fake_owned)
    called = {"n": 0}
    monkeypatch.setattr("app.api.v1.action_plans.router.generate_explicacion",
                        lambda *a, **k: (called.__setitem__("n", called["n"] + 1) or {}))

    db = AsyncMock()
    app.dependency_overrides[get_db] = _dbov(db); app.dependency_overrides[get_current_user_id] = _uov
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.post(f"/api/v1/tasks/{task.id}/explicacion")
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 200
    assert r.json()["que_es"] == "ya"
    assert called["n"] == 0   # cacheada → no llamó al generador


@pytest.mark.asyncio
async def test_explicacion_genera_y_guarda(monkeypatch):
    task = MagicMock()
    task.id = uuid.uuid4(); task.title = "Lanzar campaña"; task.objective_id = None
    task.kpi_ref = None; task.explicacion = None

    async def fake_owned(tid, uid, db):
        return task
    monkeypatch.setattr("app.api.v1.action_plans.router._get_user_task_or_404", fake_owned)
    monkeypatch.setattr("app.api.v1.action_plans.router.generate_explicacion",
                        lambda *a, **k: {"tiempo": "~3 h", "dificultad": "Media", "que_es": "x", "como": ["p1"]})

    db = AsyncMock(); db.commit = AsyncMock()
    # _objetivo_empresa loads Objective + onboarding → db.execute used; make it return None-ish
    res = MagicMock(); res.scalar_one_or_none.return_value = None
    res.scalars.return_value.first.return_value = None
    db.execute = AsyncMock(return_value=res)

    app.dependency_overrides[get_db] = _dbov(db); app.dependency_overrides[get_current_user_id] = _uov
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.post(f"/api/v1/tasks/{task.id}/explicacion")
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 200
    assert r.json()["que_es"] == "x"
    assert task.explicacion["que_es"] == "x"   # guardada en la tarea
```

- [ ] **Step 6: Endpoint en `action_plans/router.py`**

READ el archivo. Agregar imports:
```python
from sqlalchemy.orm.attributes import flag_modified
from app.models.annual_plan import Objective
from app.models.onboarding_session import OnboardingSession
from app.services.ai.task_explainer import generate_explicacion
import anyio
```
(Varios pueden estar ya importados — no duplicar.)

Agregar (después de `update_task`):
```python
async def _objetivo_empresa(task, user_id, db):
    objetivo = ""
    if task.objective_id is not None:
        obj = (await db.execute(select(Objective).where(Objective.id == task.objective_id))).scalar_one_or_none()
        objetivo = obj.title if obj else ""
    onb = (await db.execute(
        select(OnboardingSession).where(OnboardingSession.user_id == user_id)
        .order_by(OnboardingSession.created_at.desc())
    )).scalars().first()
    empresa = (((onb.memory_buffer if onb else {}) or {}).get("company") or {}).get("name") or ""
    return objetivo, empresa


@router.post("/tasks/{task_id}/explicacion")
async def explicar_tarea(
    task_id: uuid.UUID,
    user_id: str = Depends(get_current_user_id), db: AsyncSession = Depends(get_db),
):
    task = await _get_user_task_or_404(task_id, user_id, db)
    if task.explicacion:
        return task.explicacion
    objetivo, empresa = await _objetivo_empresa(task, user_id, db)
    data = await anyio.to_thread.run_sync(
        lambda: generate_explicacion(task.title, objetivo, empresa, task.kpi_ref))
    task.explicacion = data
    flag_modified(task, "explicacion")
    await db.commit()
    return data
```
(Confirmar que `select`, `uuid`, `Depends`, `get_current_user_id`, `get_db`, `AsyncSession`, `_get_user_task_or_404` ya están en el router.)

- [ ] **Step 7: Correr (pasa) + suite**

Run: `cd backend && ./venv/bin/pytest tests/unit/test_task_explainer.py tests/integration/test_task_explicacion_api.py -q && ./venv/bin/pytest -q`

- [ ] **Step 8: Commit**

```bash
git add backend/app/models/action_plan.py backend/scripts/alter_task_explicacion.py backend/app/services/ai/task_explainer.py backend/app/api/v1/action_plans/router.py backend/app/schemas/action_plan.py backend/tests/unit/test_task_explainer.py backend/tests/integration/test_task_explicacion_api.py
git commit -m "feat(plan-camino): tareas explicadas bajo demanda (columna + generador + endpoint cacheado)"
```

---

### Task 2: Generación del plan informada por FODA + metas

**Files:**
- Create: `backend/app/services/ai/foda_into_plan.py` (`augment_buffer_with_foda`)
- Modify: `backend/app/tasks/annual_plan_tasks.py` (`_run_generation` carga FODA+metas y aumenta el buffer)
- Test: `backend/tests/unit/test_foda_into_plan.py`

**Interfaces:**
- Produces: `augment_buffer_with_foda(memory_buffer: dict, foda: dict|None, metas_orden: list) -> dict` (devuelve un buffer nuevo con el `ai_context.company_narrative` enriquecido).

- [ ] **Step 1: Test**

`backend/tests/unit/test_foda_into_plan.py`:
```python
from app.services.ai.foda_into_plan import augment_buffer_with_foda


def test_augment_inyecta_foda_y_metas_en_narrative():
    mb = {"company": {"name": "X"}, "ai_context": {"company_narrative": "Empresa X."}}
    foda = {"fortalezas": ["Buen equipo"], "debilidades": ["Márgenes bajos"],
            "oportunidades": ["Mercado online"], "amenazas": ["Aranceles"]}
    out = augment_buffer_with_foda(mb, foda, ["Quiero más clientes", "Quiero reducir costos"])
    narr = out["ai_context"]["company_narrative"]
    assert "Empresa X." in narr                 # conserva lo previo
    assert "Márgenes bajos" in narr             # FODA inyectado
    assert "Quiero más clientes" in narr        # metas inyectadas
    # no muta el original
    assert "Márgenes bajos" not in mb["ai_context"]["company_narrative"]


def test_augment_sin_foda_devuelve_buffer_equivalente():
    mb = {"company": {"name": "X"}}
    out = augment_buffer_with_foda(mb, None, [])
    assert out.get("company", {}).get("name") == "X"
```

- [ ] **Step 2: Correr (falla)**

Run: `cd backend && ./venv/bin/pytest tests/unit/test_foda_into_plan.py -q`

- [ ] **Step 3: Implementar `foda_into_plan.py`**

`backend/app/services/ai/foda_into_plan.py`:
```python
"""Inyecta el FODA + metas priorizadas en el memory_buffer (vía company_narrative) para que el
generador de plan a 3 años (que ya lee company_narrative) alinee objetivos/tareas a lo prioritario."""
import copy


def augment_buffer_with_foda(memory_buffer: dict, foda: dict | None, metas_orden: list) -> dict:
    mb = copy.deepcopy(memory_buffer or {})
    if not foda and not metas_orden:
        return mb
    partes = []
    if foda:
        for k, label in (("fortalezas", "Fortalezas"), ("debilidades", "Debilidades"),
                         ("oportunidades", "Oportunidades"), ("amenazas", "Amenazas")):
            items = [str(x) for x in (foda.get(k) or []) if str(x).strip()]
            if items:
                partes.append(f"{label}: " + "; ".join(items) + ".")
    if metas_orden:
        metas = [str(m) for m in metas_orden if str(m).strip()]
        if metas:
            partes.append("Prioridades del dueño (en orden): " + " > ".join(metas) + ".")
    if not partes:
        return mb
    ai = dict(mb.get("ai_context") or {})
    prev = str(ai.get("company_narrative") or "").strip()
    bloque = "ANÁLISIS FODA Y PRIORIDADES:\n" + "\n".join(partes)
    ai["company_narrative"] = (prev + "\n\n" + bloque) if prev else bloque
    mb["ai_context"] = ai
    return mb
```

- [ ] **Step 4: Wire en `_run_generation`**

En `backend/app/tasks/annual_plan_tasks.py`, READ `_run_generation` y donde carga `memory_buffer` (del onboarding), justo después agregar la carga del FODA + metas del diagnóstico y aumentar el buffer:
```python
        from app.models.diagnostico_estrategico import DiagnosticoEstrategico
        from app.services.ai.foda_into_plan import augment_buffer_with_foda
        diag = (await db.execute(
            select(DiagnosticoEstrategico).where(DiagnosticoEstrategico.user_id == user_id)
            .order_by(DiagnosticoEstrategico.created_at.desc())
        )).scalars().first()
        dcont = (diag.content if diag else {}) or {}
        memory_buffer = augment_buffer_with_foda(memory_buffer, dcont.get("foda"), dcont.get("metas_orden") or [])
```
(Usar el nombre real de la variable del user_id y de la sesión `db` en ese bloque. `select` ya está importado en ese módulo; si no, agregarlo. Colocarlo donde `memory_buffer` ya esté cargado y ANTES de llamar a `generate_milestones`/`generate_quarter_plan`.)

- [ ] **Step 5: Correr (pasa) + suite**

Run: `cd backend && ./venv/bin/pytest tests/unit/test_foda_into_plan.py -q && ./venv/bin/pytest -q`
Expected: PASS (la generación sigue funcionando; sin FODA el buffer queda equivalente).

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/ai/foda_into_plan.py backend/app/tasks/annual_plan_tasks.py backend/tests/unit/test_foda_into_plan.py
git commit -m "feat(plan-camino): la generación del plan se informa del FODA + metas priorizadas"
```

---

## Self-Review (cobertura del spec, Plan A)

- **Tareas explicadas bajo demanda + cache (Comp.2)** → Task 1 (`explicacion` + `task_explainer` + endpoint cacheado). ✅
- **Generación informada por FODA + metas (Comp.1)** → Task 2 (`augment_buffer_with_foda` + wire en `_run_generation`). ✅
- **Sin tocar el motor / sin migración mayor** → columna vía alter script; FODA vía `company_narrative` (no se tocan firmas de los generadores). ✅
- **Entrada desde FODA + UI Camino/Timeline (Comp.3)** → NO en este plan; es el **Plan B** (frontend). ✔ (fuera de alcance declarado)
- **Marcar hecha (estado + candado evidencia)** → reutiliza `PATCH /tasks/{id}` + evidencias existentes; el Plan B (UI) lo consume. ✔

Consistencia de tipos: `generate_explicacion(...) -> {tiempo,dificultad,que_es,como}` ↔ se guarda en `ActionTask.explicacion` ↔ lo expone `ActionTaskOut.explicacion` y el endpoint. `augment_buffer_with_foda(memory_buffer, foda, metas_orden)` devuelve un buffer con `ai_context.company_narrative` enriquecido — leído por `_build_company_context` del generador.

Puntos a verificar al implementar: que `JSONB` esté importado en `action_plan.py`; que `_task_to_out`/`ActionTaskOut` incluyan `explicacion`; los nombres reales de variables en `_run_generation`; correr `alter_task_explicacion.py` en prod al desplegar.
