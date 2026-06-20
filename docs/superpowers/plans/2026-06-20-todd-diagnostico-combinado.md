# Todd — Diagnóstico combinado (Plan 2) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Que al cerrar la entrevista con Todd se genere automáticamente el **diagnóstico combinado** = autoevaluación interna (fortalezas/debilidades por área que Todd recogió) **integrada con** la investigación web (Opus + web_search), y que esas fortalezas/debilidades se muestren en la vista del diagnóstico.

**Architecture:** Las fortalezas/debilidades ya vienen clasificadas por Todd en `memory_buffer["hallazgos"]` (lo escribe `state_to_memory_buffer` al cerrar). El motor del diagnóstico (`generate_diagnostico`) las inyecta en el prompt para que el análisis web las integre, y las adjunta tal cual al `content` para mostrarlas. `todd_close` deja de solo marcar el onboarding completo: ahora también crea un `DiagnosticoEstrategico` y dispara la task de Celery existente. El frontend muestra las fortalezas/debilidades por área en la vista que ya existe.

**Tech Stack:** FastAPI, SQLAlchemy async, Celery, Anthropic (Opus 4.8 + web_search con streaming, ya arreglado). Next.js 16 App Router. Sin migración (todo en `DiagnosticoEstrategico.content` JSONB que ya existe).

## Global Constraints

- **Sin migración de esquema** — las fortalezas/debilidades viven dentro de `DiagnosticoEstrategico.content` (JSONB existente). Nada de Alembic ni tablas nuevas.
- **Retrocompatible** — diagnósticos viejos sin `fortalezas_debilidades` en su `content` → el GET devuelve `{}` y la vista no muestra esa sección. No romper el flujo del diagnóstico que ya existe (`/diagnostico/generate`).
- **Modelo:** Opus 4.8 (`settings.DIAGNOSTICO_AI_MODEL`) para el diagnóstico — sin cambios al motor de red (streaming ya aplicado).
- **`hallazgos` shape:** `{ "<area>": [ {"tipo": "fortaleza|debilidad|parcial", "texto": str}, ... ] }` — tal como lo produce el agente de Todd.

---

### Task 1: El motor del diagnóstico integra y adjunta las fortalezas/debilidades internas

**Files:**
- Modify: `backend/app/services/ai/diagnostico_estrategico.py` (`build_prompt`, `generate_diagnostico`, `SYSTEM_PROMPT`; nuevo helper `attach_internal_findings`)
- Test: `backend/tests/unit/test_diagnostico_internal.py` (crear)

**Interfaces:**
- Produces:
  - `attach_internal_findings(content: dict, memory_buffer: dict) -> dict` — agrega `content["fortalezas_debilidades"] = memory_buffer["hallazgos"]` (o `{}`).
  - `build_prompt(memory_buffer)` ahora incluye un bloque con los hallazgos internos.

- [ ] **Step 1: Tests**

`backend/tests/unit/test_diagnostico_internal.py`:
```python
from app.services.ai.diagnostico_estrategico import build_prompt, attach_internal_findings


def test_build_prompt_incluye_hallazgos_internos():
    mb = {
        "company": {"name": "Keting Media", "industry": "Apps", "website": "https://k.mx",
                    "competitors": ["Wizeline"]},
        "hallazgos": {
            "financiero": [{"tipo": "debilidad", "texto": "Márgenes apretados"}],
            "comercial": [{"tipo": "fortaleza", "texto": "Cartera diversificada"}],
        },
    }
    p = build_prompt(mb)
    assert "Keting Media" in p
    assert "Márgenes apretados" in p          # hallazgo interno inyectado
    assert "fortaleza" in p.lower() or "debilidad" in p.lower()


def test_build_prompt_sin_hallazgos_no_truena():
    p = build_prompt({"company": {"name": "X"}})
    assert "X" in p


def test_attach_internal_findings_pega_hallazgos():
    content = {"sections": [{"key": "resumen_ejecutivo", "title": "R", "body": "..."}], "sources": []}
    mb = {"hallazgos": {"rh": [{"tipo": "parcial", "texto": "Sin plan DNC"}]}}
    out = attach_internal_findings(content, mb)
    assert out["fortalezas_debilidades"]["rh"][0]["texto"] == "Sin plan DNC"
    # no pisa lo demás
    assert out["sections"][0]["key"] == "resumen_ejecutivo"


def test_attach_internal_findings_sin_hallazgos_es_dict_vacio():
    out = attach_internal_findings({"sections": [], "sources": []}, {})
    assert out["fortalezas_debilidades"] == {}
```

- [ ] **Step 2: Correr (falla)**

Run: `cd backend && ./venv/bin/pytest tests/unit/test_diagnostico_internal.py -q`
Expected: FAIL (`attach_internal_findings` no existe; `build_prompt` no inyecta hallazgos).

- [ ] **Step 3: Implementar**

En `backend/app/services/ai/diagnostico_estrategico.py`:

1. Reemplazar `build_prompt` por esta versión (agrega el bloque de hallazgos internos):
```python
def build_prompt(memory_buffer: dict) -> str:
    c = (memory_buffer or {}).get("company", {}) or {}
    loc = c.get("location", {}) or {}
    region = ", ".join(x for x in [loc.get("city"), loc.get("state"), loc.get("country")] if x)
    competidores = c.get("competitors") or []

    hallazgos = (memory_buffer or {}).get("hallazgos") or {}
    bloque_interno = ""
    if hallazgos:
        lineas = []
        for area, items in hallazgos.items():
            for h in (items or []):
                tipo = str(h.get("tipo", "")).strip()
                texto = str(h.get("texto", "")).strip()
                if texto:
                    lineas.append(f"  - [{area} · {tipo}] {texto}")
        if lineas:
            bloque_interno = (
                "\nAUTOEVALUACIÓN INTERNA (lo que el dueño le contó a Todd en la entrevista — "
                "fortalezas/debilidades por área). INTÉGRALA con lo que encuentres en la web "
                "(confírmala, contextualízala o matízala con datos del sector):\n"
                + "\n".join(lineas) + "\n"
            )

    return (
        f"Empresa: {c.get('name', 'N/D')}\n"
        f"Industria: {c.get('industry', 'N/D')}\n"
        f"Región donde opera: {region or 'N/D'}\n"
        f"Sitio web: {c.get('website', 'N/D')}\n"
        f"Competidores que el usuario CREE tener: {', '.join(competidores) if competidores else 'ninguno indicado'}\n"
        f"{bloque_interno}\n"
        "Investiga y entrega el diagnóstico en el JSON indicado."
    )
```

2. Agregar el helper (cerca de `_diagnostico_vacio`):
```python
def attach_internal_findings(content: dict, memory_buffer: dict) -> dict:
    """Adjunta al content las fortalezas/debilidades que Todd recogió (memory_buffer['hallazgos'])."""
    content["fortalezas_debilidades"] = (memory_buffer or {}).get("hallazgos") or {}
    return content
```

3. En `generate_diagnostico`, donde hace `if not _diagnostico_vacio(content): return content`, cambiarlo a:
```python
        content = parse_diagnostico(raw)
        if not _diagnostico_vacio(content):
            return attach_internal_findings(content, memory_buffer)
```

4. En `SYSTEM_PROMPT`, después de la línea que habla de "Competencia percibida vs. real", agregar un párrafo:
```
Si recibes una AUTOEVALUACIÓN INTERNA (fortalezas/debilidades que el dueño declaró), intégrala en
tu análisis: en 'conclusiones' y en las secciones relevantes, confirma, matiza o contrasta esas
afirmaciones con lo que encuentres en la web. No te limites a repetirlas; agrégales contexto del sector.
```

- [ ] **Step 4: Correr (pasa) + suite del diagnóstico**

Run: `cd backend && ./venv/bin/pytest tests/unit/test_diagnostico_internal.py tests/unit/test_diagnostico_engine.py tests/unit/test_diagnostico_completeness.py -q`
Expected: PASS (los tests existentes del diagnóstico siguen verdes; `build_prompt` sigue funcionando sin hallazgos).

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/ai/diagnostico_estrategico.py backend/tests/unit/test_diagnostico_internal.py
git commit -m "feat(todd-dx): el diagnóstico integra y adjunta las fortalezas/debilidades de la entrevista"
```

---

### Task 2: Exponer `fortalezas_debilidades` por la API

**Files:**
- Modify: `backend/app/schemas/diagnostico.py` (`DiagnosticoOut`)
- Modify: `backend/app/api/v1/diagnostico/router.py` (`get_diagnostico`)
- Test: `backend/tests/integration/test_diagnostico_api.py` (agregar un test) — si no existe el archivo, crearlo con el patrón de abajo.

**Interfaces:**
- Consumes: `content["fortalezas_debilidades"]` (Task 1).
- Produces: `DiagnosticoOut.fortalezas_debilidades: dict` y el GET `/diagnostico` lo devuelve.

- [ ] **Step 1: Test**

Agregar a `backend/tests/integration/test_diagnostico_api.py` (si el archivo no existe, créalo con estos imports + test):
```python
import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.core.dependencies import get_current_user_id, get_db

MOCK_USER_ID = "user_test_dx_fd"


def _db_override(db):
    async def override():
        yield db
    return override


async def _user_override():
    return MOCK_USER_ID


@pytest.mark.asyncio
async def test_get_diagnostico_devuelve_fortalezas_debilidades():
    diag = MagicMock()
    diag.status = "active"
    diag.fail_reason = None
    diag.created_at = None
    diag.content = {
        "sections": [{"key": "resumen_ejecutivo", "title": "Resumen", "body": "ok"}],
        "sources": [],
        "fortalezas_debilidades": {"financiero": [{"tipo": "debilidad", "texto": "Márgenes apretados"}]},
    }
    res = MagicMock(); res.scalars.return_value.first.return_value = diag
    db = AsyncMock(); db.execute = AsyncMock(return_value=res); db.commit = AsyncMock()

    app.dependency_overrides[get_db] = _db_override(db)
    app.dependency_overrides[get_current_user_id] = _user_override
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.get("/api/v1/diagnostico")
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 200
    body = r.json()
    assert body["fortalezas_debilidades"]["financiero"][0]["texto"] == "Márgenes apretados"
```

- [ ] **Step 2: Correr (falla)**

Run: `cd backend && ./venv/bin/pytest tests/integration/test_diagnostico_api.py::test_get_diagnostico_devuelve_fortalezas_debilidades -q`
Expected: FAIL (`fortalezas_debilidades` no está en la respuesta).

- [ ] **Step 3: Implementar**

En `backend/app/schemas/diagnostico.py`, agregar el campo a `DiagnosticoOut`:
```python
class DiagnosticoOut(BaseModel):
    status: str
    fail_reason: str | None = None
    sections: list[DiagnosticoSection] = []
    sources: list[DiagnosticoSource] = []
    fortalezas_debilidades: dict = {}
```

En `backend/app/api/v1/diagnostico/router.py`, en `get_diagnostico`, incluir el campo al construir `DiagnosticoOut`:
```python
    content = diag.content or {}
    return DiagnosticoOut(
        status=diag.status, fail_reason=diag.fail_reason,
        sections=content.get("sections", []), sources=content.get("sources", []),
        fortalezas_debilidades=content.get("fortalezas_debilidades", {}),
    )
```

- [ ] **Step 4: Correr (pasa) + suite**

Run: `cd backend && ./venv/bin/pytest tests/integration/test_diagnostico_api.py -q && ./venv/bin/pytest -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/schemas/diagnostico.py backend/app/api/v1/diagnostico/router.py backend/tests/integration/test_diagnostico_api.py
git commit -m "feat(todd-dx): exponer fortalezas_debilidades en GET /diagnostico"
```

---

### Task 3: `todd_close` dispara el diagnóstico combinado

**Files:**
- Modify: `backend/app/api/v1/todd/router.py` (`todd_close`)
- Test: `backend/tests/integration/test_todd_api.py` (actualizar `test_close_escribe_memory_buffer_y_marca_onboarding`)

**Interfaces:**
- Consumes: `DiagnosticoEstrategico`, `generate_diagnostico_task` (existentes).

- [ ] **Step 1: Actualizar el test de cierre**

En `backend/tests/integration/test_todd_api.py`, reemplazar el cuerpo de `test_close_escribe_memory_buffer_y_marca_onboarding` para que también verifique que se crea un diagnóstico y se encola la task. Nueva versión completa de ese test:
```python
@pytest.mark.asyncio
async def test_close_escribe_memory_buffer_y_dispara_diagnostico(monkeypatch):
    sess = MagicMock()
    sess.user_id = MOCK_USER_ID
    sess.status = "active"
    sess.state = {"company": {"name": "Keting Media"}, "areas_cubiertas": [],
                  "hallazgos": {"financiero": [{"tipo": "debilidad", "texto": "Márgenes"}]}}
    onb = MagicMock(); onb.user_id = MOCK_USER_ID
    # 1ª query: ToddSession; 2ª: OnboardingSession; 3ª: diagnóstico previo (none)
    r1 = MagicMock(); r1.scalar_one_or_none.return_value = sess
    r2 = MagicMock(); r2.scalars.return_value.first.return_value = onb
    r3 = MagicMock(); r3.scalars.return_value.first.return_value = None
    db = AsyncMock(); db.execute = AsyncMock(side_effect=[r1, r2, r3])
    db.add = MagicMock(); db.flush = AsyncMock(); db.commit = AsyncMock()

    dispatched = {}
    class _FakeTask:
        def delay(self, diag_id):
            dispatched["id"] = diag_id
    monkeypatch.setattr("app.tasks.diagnostico_tasks.generate_diagnostico_task", _FakeTask())

    app.dependency_overrides[get_db] = _db_override(db)
    app.dependency_overrides[get_current_user_id] = _user_override
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.post("/api/v1/onboarding/todd/close")
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 200
    assert sess.status == "done"
    assert onb.memory_buffer["company"]["name"] == "Keting Media"
    assert onb.completed_stages == [1, 2, 3, 4, 5, 6, 7, 8]
    assert db.add.called          # creó el DiagnosticoEstrategico
    assert "id" in dispatched     # encoló la task
```

- [ ] **Step 2: Correr (falla)**

Run: `cd backend && ./venv/bin/pytest tests/integration/test_todd_api.py::test_close_escribe_memory_buffer_y_dispara_diagnostico -q`
Expected: FAIL (hoy `todd_close` no crea diagnóstico ni encola).

- [ ] **Step 3: Implementar**

En `backend/app/api/v1/todd/router.py`, agregar el import del modelo (arriba):
```python
from app.models.diagnostico_estrategico import DiagnosticoEstrategico
```
y reemplazar el final de `todd_close` (el bloque que tiene el `# TODO (Plan 2)` y el `return {"ok": True}`) por:
```python
    await db.commit()

    # Disparar el diagnóstico combinado (interno + web). Reemplaza el diagnóstico previo si lo hubiera.
    prev = (await db.execute(
        select(DiagnosticoEstrategico).where(DiagnosticoEstrategico.user_id == user_id)
        .order_by(DiagnosticoEstrategico.created_at.desc())
    )).scalars().first()
    if prev is not None:
        await db.delete(prev)
        await db.flush()
    diag = DiagnosticoEstrategico(user_id=user_id, status="generating")
    db.add(diag)
    await db.flush()
    await db.commit()
    try:
        from app.tasks.diagnostico_tasks import generate_diagnostico_task
        generate_diagnostico_task.delay(str(diag.id))
    except Exception:
        diag.status = "failed"
        diag.fail_reason = "no se pudo encolar"
        await db.commit()
    return {"ok": True}
```
(Quitar el comentario `# TODO (Plan 2)`. El `onb.memory_buffer`/`completed_stages` se siguen escribiendo y commiteando ANTES, para que la task lea el memory_buffer ya con los hallazgos.)

> Confirmar que `select` y `DiagnosticoEstrategico` quedan importados en el router. El `generate_diagnostico_task` se importa lazy dentro del try (igual que en `generate_diagnostico_endpoint`).

- [ ] **Step 4: Correr (pasa) + suite**

Run: `cd backend && ./venv/bin/pytest tests/integration/test_todd_api.py -q && ./venv/bin/pytest -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/api/v1/todd/router.py backend/tests/integration/test_todd_api.py
git commit -m "feat(todd-dx): al cerrar la entrevista, Todd dispara el diagnóstico combinado"
```

---

### Task 4: Frontend — mostrar fortalezas/debilidades por área

**Files:**
- Modify: `frontend/src/lib/diagnostico.ts` (tipos)
- Modify: `frontend/src/app/dashboard/diagnostico/page.tsx` (vista)
- Test: `npm run lint` + `npm run build`

**Interfaces:**
- Consumes: `GET /diagnostico` ahora trae `fortalezas_debilidades`.

- [ ] **Step 1: Tipos en `lib/diagnostico.ts`**

En `frontend/src/lib/diagnostico.ts`, agregar el tipo y el campo en `Diagnostico`:
```typescript
export interface Hallazgo {
  tipo: string
  texto: string
}

export interface Diagnostico {
  status: DiagnosticoStatus
  fail_reason: string | null
  sections: DiagnosticoSection[]
  sources: DiagnosticoSource[]
  fortalezas_debilidades: Record<string, Hallazgo[]>
}
```
(Agregar `fortalezas_debilidades` a la interface `Diagnostico` existente — mantener el resto igual.)

- [ ] **Step 2: Render en la vista**

En `frontend/src/app/dashboard/diagnostico/page.tsx`, READ el archivo y, justo ANTES del bloque de `sources` (el `{(diag?.sources ?? []).length > 0 && (`), insertar una sección que liste las fortalezas/debilidades por área:
```tsx
          {Object.keys(diag?.fortalezas_debilidades ?? {}).length > 0 && (
            <section className="space-y-3">
              <h2 className="text-xl font-bold text-black tracking-tight">Fortalezas y debilidades</h2>
              <div className="grid gap-4 sm:grid-cols-2">
                {Object.entries(diag!.fortalezas_debilidades).map(([area, items]) => (
                  <div key={area} className="border border-gray-100 rounded-2xl p-4">
                    <p className="text-xs font-medium tracking-widest text-gray-400 uppercase mb-2">{area}</p>
                    <ul className="space-y-1.5">
                      {items.map((h, j) => (
                        <li key={j} className="flex items-start gap-2 text-sm">
                          <span className={
                            h.tipo === "fortaleza" ? "text-green-600"
                            : h.tipo === "debilidad" ? "text-red-500" : "text-amber-500"
                          }>
                            {h.tipo === "fortaleza" ? "▲" : h.tipo === "debilidad" ? "▼" : "■"}
                          </span>
                          <span className="text-gray-700">{h.texto}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                ))}
              </div>
            </section>
          )}
```
(Confirmar el nombre real de la variable del diagnóstico en ese archivo — el grep mostró `diag?.sections`/`diag!.sources`, así que es `diag`. Insertar la sección dentro del mismo contenedor donde se renderizan `sections`/`sources`.)

- [ ] **Step 3: lint + build**

Run: `cd frontend && npm run lint` (por separado) y `cd frontend && npm run build`.
Expected: el build compila (exit 0); `lib/diagnostico.ts` y `dashboard/diagnostico/page.tsx` sin errores nuevos de lint (los problemas pre-existentes en otros archivos no cuentan — grep el output por `diagnostico` para confirmar limpio).

- [ ] **Step 4: Commit**

```bash
git add frontend/src/lib/diagnostico.ts frontend/src/app/dashboard/diagnostico/page.tsx
git commit -m "feat(todd-dx-fe): mostrar fortalezas/debilidades por área en el diagnóstico"
```

---

## Self-Review (cobertura del spec, Plan 2 = Componente 4)

- **Diagnóstico combinado interno + web (Opus)** → Task 1 (`build_prompt` inyecta hallazgos + `SYSTEM_PROMPT` instruye integrarlos). ✅
- **content extendido con fortalezas/debilidades por área** → Task 1 (`attach_internal_findings`) + Task 2 (API lo expone). ✅
- **Disparar el diagnóstico al cerrar Todd** → Task 3 (`todd_close` crea diag + `.delay`, quita el TODO). ✅
- **Vista ampliada con fortalezas/debilidades** → Task 4. ✅
- **Reusa el motor con streaming ya arreglado** → sí, no se toca la red del motor. ✅
- **Sin migración / retrocompatible** → `fortalezas_debilidades` vive en `content`; GET default `{}`; diagnósticos viejos sin él no rompen. ✅

Consistencia de tipos: `attach_internal_findings(content, memory_buffer)` setea `content["fortalezas_debilidades"]` = `hallazgos` (`{area: [{tipo, texto}]}`); `DiagnosticoOut.fortalezas_debilidades: dict` lo devuelve; el front lo tipa `Record<string, {tipo, texto}[]>`. El flujo de datos: Todd close escribe `memory_buffer["hallazgos"]` (vía `state_to_memory_buffer`, ya existe) → crea diag → la task carga ese memory_buffer → `generate_diagnostico` lo inyecta y lo adjunta.

Pendiente a verificar al implementar: que `select` y `DiagnosticoEstrategico` queden importados en el router de Todd; que el archivo `tests/integration/test_diagnostico_api.py` exista (si no, crearlo con el patrón dado); el nombre de la variable del diagnóstico en la página del front (`diag`). Nota: el diagnóstico tarda minutos (Opus+web) → la página de diagnóstico ya hace polling de `/diagnostico/status`, así que la vista de carga ya funciona; tras cerrar Todd la UI navega a `/dashboard/diagnostico` (ya lo hace el botón Finalizar del Plan 1).
