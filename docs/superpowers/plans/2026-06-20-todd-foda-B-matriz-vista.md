# Todd FODA — Plan B: generación de la matriz + vista — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Al confirmar la priorización de metas, generar (Opus, sin web) una **matriz FODA** que cruza lo interno (fortalezas/debilidades) con lo externo (oportunidades/amenazas) + las metas priorizadas, y mostrarla en una **vista propia 2×2** de alta calidad visual.

**Architecture:** Una síntesis de Opus (`generate_foda`) combina los hallazgos internos del diagnóstico, los factores externos (PESTEL) y el ranking de metas — todo ya persistido en `DiagnosticoEstrategico.content` por el Plan A. Corre async (Celery, como el diagnóstico) y se guarda en `content["foda"]` con `content["foda_status"]`. El frontend tiene una página `/dashboard/foda` que hace polling y renderiza la matriz.

**Tech Stack:** FastAPI, SQLAlchemy async, Celery, anthropic (Opus 4.8 = `settings.DIAGNOSTICO_AI_MODEL`, **sin web_search**, tool use forzado). Next.js 16 App Router, framer-motion. Sin migración (todo en `content` JSONB).

## Global Constraints

- **Sin nueva búsqueda web** en el FODA — sintetiza lo ya reunido. **Sin migración** — `foda`, `foda_status`, `factores_externos`, `metas_orden` viven en `DiagnosticoEstrategico.content`.
- **Estructura FODA:** `{"fortalezas":[str],"oportunidades":[str],"debilidades":[str],"amenazas":[str],"sintesis":str,"metas_priorizadas":[str]}`.
- **Fallback determinista:** si no hay API key o el LLM falla, la FODA se arma de los `hallazgos` (F/D) + `factores_externos` (O/A) + `metas_orden` — nunca queda vacía.
- **Calidad de la vista:** la matriz FODA es el entregable visible; debe verse premium y on-brand (`--gob-navy`/`--gob-bone`/`--gob-ink`), no genérica.
- **Reusa el patrón del diagnóstico** (status generating/active/failed + polling).

---

### Task 1: Motor del FODA (`generate_foda` + fallback determinista)

**Files:**
- Create: `backend/app/services/ai/foda.py`
- Test: `backend/tests/unit/test_foda.py` (crear)

**Interfaces:**
- Produces:
  - `_foda_fallback(hallazgos: dict, factores_externos: dict, metas_orden: list) -> dict`
  - `generate_foda(memory_buffer: dict, diagnostico_content: dict, factores_externos: dict, metas_orden: list) -> dict`

- [ ] **Step 1: Tests**

`backend/tests/unit/test_foda.py`:
```python
from app.services.ai.foda import _foda_fallback, generate_foda


HALLAZGOS = {
    "financiero": [{"tipo": "debilidad", "texto": "Márgenes apretados"}],
    "comercial": [{"tipo": "fortaleza", "texto": "Buen portafolio"},
                  {"tipo": "parcial", "texto": "Marca poco reconocida"}],
}
FACTORES = {
    "economicos": [{"tipo": "amenaza", "texto": "Nuevos aranceles"}],
    "tecnologicos": [{"tipo": "oportunidad", "texto": "Ventas online en auge"}],
}
METAS = ["Quiero más clientes", "Quiero reducir costos"]


def test_fallback_clasifica_interno_y_externo():
    f = _foda_fallback(HALLAZGOS, FACTORES, METAS)
    assert "Buen portafolio" in f["fortalezas"]
    assert "Márgenes apretados" in f["debilidades"]
    assert "Marca poco reconocida" in f["debilidades"]   # 'parcial' cuenta como debilidad
    assert "Ventas online en auge" in f["oportunidades"]
    assert "Nuevos aranceles" in f["amenazas"]
    assert f["metas_priorizadas"] == METAS
    assert "sintesis" in f


def test_generate_foda_sin_api_key_usa_fallback(monkeypatch):
    import app.services.ai.foda as foda
    monkeypatch.setattr(foda.settings, "ANTHROPIC_API_KEY", "")
    out = generate_foda({}, {"fortalezas_debilidades": HALLAZGOS}, FACTORES, METAS)
    assert "Buen portafolio" in out["fortalezas"]
    assert out["metas_priorizadas"] == METAS


def test_generate_foda_toma_hallazgos_del_diagnostico_o_memory(monkeypatch):
    import app.services.ai.foda as foda
    monkeypatch.setattr(foda.settings, "ANTHROPIC_API_KEY", "")
    # si el content no trae fortalezas_debilidades, usa memory_buffer['hallazgos']
    out = generate_foda({"hallazgos": HALLAZGOS}, {}, FACTORES, METAS)
    assert "Márgenes apretados" in out["debilidades"]
```

- [ ] **Step 2: Correr (falla)**

Run: `cd backend && ./venv/bin/pytest tests/unit/test_foda.py -q`

- [ ] **Step 3: Implementar `backend/app/services/ai/foda.py`**

```python
"""Motor de la matriz FODA: síntesis de lo interno (hallazgos) + externo (factores) + metas.
Opus sin web_search, salida estructurada por tool use. Fallback determinista si no hay IA."""
import json

import anthropic

from app.core.config import settings
from app.services.ai.agents.base import _create_with_retry

FODA_TOOL = {
    "name": "matriz_foda",
    "description": "Devuelve la matriz FODA de la empresa.",
    "input_schema": {
        "type": "object",
        "properties": {
            "fortalezas": {"type": "array", "items": {"type": "string"}},
            "oportunidades": {"type": "array", "items": {"type": "string"}},
            "debilidades": {"type": "array", "items": {"type": "string"}},
            "amenazas": {"type": "array", "items": {"type": "string"}},
            "sintesis": {"type": "string"},
        },
        "required": ["fortalezas", "oportunidades", "debilidades", "amenazas", "sintesis"],
    },
}


def _texts_by_tipo(d: dict, tipos: set) -> list[str]:
    out = []
    for items in (d or {}).values():
        for it in (items or []):
            if str((it or {}).get("tipo")) in tipos and str((it or {}).get("texto", "")).strip():
                out.append(str(it["texto"]).strip())
    return out


def _foda_fallback(hallazgos: dict, factores_externos: dict, metas_orden: list) -> dict:
    return {
        "fortalezas": _texts_by_tipo(hallazgos, {"fortaleza"}),
        "debilidades": _texts_by_tipo(hallazgos, {"debilidad", "parcial"}),
        "oportunidades": _texts_by_tipo(factores_externos, {"oportunidad"}),
        "amenazas": _texts_by_tipo(factores_externos, {"amenaza"}),
        "sintesis": "",
        "metas_priorizadas": [str(m) for m in (metas_orden or [])],
    }


_SYSTEM = (
    "Eres un analista estratégico senior del consejo de Gobernia. Construye la matriz FODA de la empresa "
    "en español, integrando lo INTERNO (fortalezas/debilidades de la entrevista) con lo EXTERNO "
    "(oportunidades/amenazas del entorno) y el diagnóstico. Sé concreto y accionable: 3-6 puntos por "
    "cuadrante, frases cortas. En 'sintesis' (2-3 oraciones) cruza lo más importante: cómo usar las "
    "fortalezas para las oportunidades y qué debilidades/amenazas atender primero, considerando las "
    "metas prioritarias del dueño. No inventes datos que no estén en la información dada."
)


def generate_foda(memory_buffer: dict, diagnostico_content: dict,
                  factores_externos: dict, metas_orden: list) -> dict:
    hallazgos = ((diagnostico_content or {}).get("fortalezas_debilidades")
                 or (memory_buffer or {}).get("hallazgos") or {})
    fallback = _foda_fallback(hallazgos, factores_externos, metas_orden)
    if not settings.ANTHROPIC_API_KEY:
        return fallback

    secciones = []
    for s in ((diagnostico_content or {}).get("sections") or [])[:4]:
        if s.get("body"):
            secciones.append(f"{s.get('title','')}: {s['body'][:600]}")
    user = (
        "HALLAZGOS INTERNOS:\n" + json.dumps(hallazgos, ensure_ascii=False)[:2500] + "\n\n"
        "FACTORES EXTERNOS:\n" + json.dumps(factores_externos or {}, ensure_ascii=False)[:2500] + "\n\n"
        "DIAGNÓSTICO (web):\n" + ("\n".join(secciones) or "(n/d)")[:2500] + "\n\n"
        "METAS PRIORITARIAS (en orden):\n" + json.dumps([str(m) for m in (metas_orden or [])], ensure_ascii=False)
    )
    try:
        client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY, timeout=300.0)
        response = _create_with_retry(
            client, model=settings.DIAGNOSTICO_AI_MODEL, max_tokens=2048,
            system=_SYSTEM, messages=[{"role": "user", "content": user}],
            tools=[FODA_TOOL], tool_choice={"type": "tool", "name": "matriz_foda"},
        )
        block = next((b for b in response.content if getattr(b, "type", None) == "tool_use"), None)
        d = dict(block.input) if block is not None and isinstance(block.input, dict) else {}
        if not d:
            return fallback
        return {
            "fortalezas": [str(x) for x in (d.get("fortalezas") or [])],
            "oportunidades": [str(x) for x in (d.get("oportunidades") or [])],
            "debilidades": [str(x) for x in (d.get("debilidades") or [])],
            "amenazas": [str(x) for x in (d.get("amenazas") or [])],
            "sintesis": str(d.get("sintesis") or ""),
            "metas_priorizadas": [str(m) for m in (metas_orden or [])],
        }
    except Exception:
        return fallback
```

- [ ] **Step 4: Correr (pasa)**

Run: `cd backend && ./venv/bin/pytest tests/unit/test_foda.py -q`

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/ai/foda.py backend/tests/unit/test_foda.py
git commit -m "feat(todd-foda): motor de la matriz FODA (síntesis Opus + fallback determinista)"
```

---

### Task 2: Task de Celery + disparo en `save_metas` + endpoint `GET /foda`

**Files:**
- Create: `backend/app/tasks/foda_tasks.py`
- Modify: `backend/app/tasks/worker.py` (registrar la task)
- Modify: `backend/app/api/v1/todd/router.py` (disparar en `save_metas` + endpoint `GET /foda`)
- Modify: `backend/app/schemas/todd.py` (`FodaOut`)
- Test: `backend/tests/integration/test_foda_api.py` (crear)

**Interfaces:**
- Consumes: `generate_foda` (Task 1).
- Produces: `generate_foda_task` (Celery); `GET /onboarding/foda` → `FodaOut {status, foda, metas}`.

- [ ] **Step 1: Task de Celery**

`backend/app/tasks/foda_tasks.py`:
```python
"""Task de Celery del FODA (espejo de diagnostico_tasks). Sin web, rápida."""
import asyncio

from sqlalchemy import select
from sqlalchemy.orm.attributes import flag_modified

from app.tasks.worker import celery_app
from app.models.diagnostico_estrategico import DiagnosticoEstrategico
from app.models.onboarding_session import OnboardingSession
from app.services.ai.foda import generate_foda


@celery_app.task(name="generate_foda", bind=True, max_retries=1)
def generate_foda_task(self, user_id: str) -> dict:
    try:
        return asyncio.run(_run(user_id))
    except Exception as exc:
        raise self.retry(exc=exc, countdown=20)


async def _run(user_id: str) -> dict:
    from app.db.session import task_session
    async with task_session() as db:
        diag = (await db.execute(
            select(DiagnosticoEstrategico).where(DiagnosticoEstrategico.user_id == user_id)
            .order_by(DiagnosticoEstrategico.created_at.desc())
        )).scalars().first()
        if diag is None:
            return {"status": "skipped"}
        onb = (await db.execute(
            select(OnboardingSession).where(OnboardingSession.user_id == user_id)
            .order_by(OnboardingSession.created_at.desc())
        )).scalars().first()
        memory_buffer = (onb.memory_buffer if onb else {}) or {}
        content = dict(diag.content or {})
        try:
            foda = await asyncio.to_thread(
                generate_foda, memory_buffer, content,
                content.get("factores_externos") or {}, content.get("metas_orden") or [])
            content["foda"] = foda
            content["foda_status"] = "active"
        except Exception:
            content["foda_status"] = "failed"
        diag.content = content
        flag_modified(diag, "content")
        await db.commit()
    return {"status": "active", "user_id": user_id}
```

- [ ] **Step 2: Registrar la task**

En `backend/app/tasks/worker.py`, agregar `"app.tasks.foda_tasks"` a la lista `include`:
```python
    include=["app.tasks.document_tasks", "app.tasks.annual_plan_tasks",
             "app.tasks.diagnostico_tasks", "app.tasks.foda_tasks"],
```

- [ ] **Step 3: Disparar en `save_metas` + endpoint `GET /foda` + schema**

En `backend/app/schemas/todd.py`, agregar:
```python
class FodaOut(BaseModel):
    status: str
    foda: dict | None = None
    metas: list[str] = []
```

En `backend/app/api/v1/todd/router.py`:
1. Import: agregar `FodaOut` a la línea de schemas de todd.
2. En `save_metas`, ANTES del `return {"ok": True}`, marcar generando + encolar:
```python
    content["foda_status"] = "generating"
    diag.content = content
    flag_modified(diag, "content")
    await db.commit()
    try:
        from app.tasks.foda_tasks import generate_foda_task
        generate_foda_task.delay(user_id)
    except Exception:
        content["foda_status"] = "failed"
        diag.content = content
        flag_modified(diag, "content")
        await db.commit()
    return {"ok": True}
```
(Reemplaza el bloque final actual de `save_metas` que hacía `diag.content = content; flag_modified(...); await db.commit(); return {"ok": True}` por: setear factores/metas como ya hace + `foda_status="generating"` + commit + encolar.)
3. Endpoint nuevo (después de `save_metas`):
```python
@router.get("/onboarding/foda", response_model=FodaOut)
async def get_foda(user_id: str = Depends(get_current_user_id), db: AsyncSession = Depends(get_db)):
    diag = (await db.execute(
        select(DiagnosticoEstrategico).where(DiagnosticoEstrategico.user_id == user_id)
        .order_by(DiagnosticoEstrategico.created_at.desc())
    )).scalars().first()
    if diag is None:
        raise HTTPException(status_code=404, detail="No hay análisis.")
    c = diag.content or {}
    return FodaOut(status=c.get("foda_status") or "none", foda=c.get("foda"),
                   metas=c.get("metas_orden") or [])
```

- [ ] **Step 4: Tests**

`backend/tests/integration/test_foda_api.py`:
```python
import pytest
from unittest.mock import AsyncMock, MagicMock
from httpx import ASGITransport, AsyncClient
from app.main import app
from app.core.dependencies import get_current_user_id, get_db

UID = "user_test_foda"


def _dbov(db):
    async def o():
        yield db
    return o


async def _uov():
    return UID


@pytest.mark.asyncio
async def test_get_foda_active_devuelve_matriz():
    diag = MagicMock()
    diag.content = {"foda_status": "active",
                    "foda": {"fortalezas": ["Buen portafolio"], "oportunidades": [], "debilidades": [],
                             "amenazas": [], "sintesis": "ok", "metas_priorizadas": ["Quiero más clientes"]},
                    "metas_orden": ["Quiero más clientes"]}
    res = MagicMock(); res.scalars.return_value.first.return_value = diag
    db = AsyncMock(); db.execute = AsyncMock(return_value=res)
    app.dependency_overrides[get_db] = _dbov(db); app.dependency_overrides[get_current_user_id] = _uov
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.get("/api/v1/onboarding/foda")
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "active"
    assert body["foda"]["fortalezas"] == ["Buen portafolio"]
    assert body["metas"] == ["Quiero más clientes"]


@pytest.mark.asyncio
async def test_save_metas_dispara_foda(monkeypatch):
    diag = MagicMock(); diag.content = {"sections": []}
    externo = MagicMock(); externo.state = {"factores_externos": {}}
    rdiag = MagicMock(); rdiag.scalars.return_value.first.return_value = diag
    rext = MagicMock(); rext.scalar_one_or_none.return_value = externo
    db = AsyncMock(); db.execute = AsyncMock(side_effect=[rdiag, rext]); db.commit = AsyncMock()

    dispatched = {}
    class _Fake:
        def delay(self, uid):
            dispatched["uid"] = uid
    monkeypatch.setattr("app.tasks.foda_tasks.generate_foda_task", _Fake())

    app.dependency_overrides[get_db] = _dbov(db); app.dependency_overrides[get_current_user_id] = _uov
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.post("/api/v1/onboarding/todd/metas", json={"orden": ["Quiero más clientes"]})
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 200
    assert diag.content["foda_status"] == "generating"
    assert dispatched.get("uid") == UID
```

- [ ] **Step 5: Correr (pasa) + suite**

Run: `cd backend && ./venv/bin/pytest tests/integration/test_foda_api.py tests/integration/test_todd_externo_api.py -q && ./venv/bin/pytest -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/tasks/foda_tasks.py backend/app/tasks/worker.py backend/app/api/v1/todd/router.py backend/app/schemas/todd.py backend/tests/integration/test_foda_api.py
git commit -m "feat(todd-foda): task de Celery del FODA + disparo en metas + GET /foda"
```

---

### Task 3: Frontend — vista de la matriz FODA (premium) + sidebar + redirect

**Files:**
- Create: `frontend/src/lib/foda.ts`
- Create: `frontend/src/app/dashboard/foda/page.tsx`
- Modify: `frontend/src/components/ui/Sidebar.tsx` (ítem "FODA")
- Modify: `frontend/src/app/onboarding/todd/metas/page.tsx` (redirect a `/dashboard/foda`)
- Test: `npm run lint` + `npm run build`

**Interfaces:**
- Consumes: `GET /onboarding/foda` (Task 2).

**Diseño (UX):** matriz 2×2 on-brand. Cuadrantes con encabezado e ícono y un color de acento sobrio por tipo: **Fortalezas** verde, **Oportunidades** azul (navy), **Debilidades** ámbar, **Amenazas** rojo — usados solo en el borde/encabezado (fondo claro, texto oscuro; nada chillón). Arriba, la **síntesis** en una tarjeta destacada; abajo, las **metas priorizadas** numeradas. Estado de carga elegante mientras `generating`.

- [ ] **Step 1: Cliente `lib/foda.ts`**

```typescript
import api from "@/lib/api"

export interface Foda {
  fortalezas: string[]
  oportunidades: string[]
  debilidades: string[]
  amenazas: string[]
  sintesis: string
  metas_priorizadas: string[]
}

export interface FodaOut {
  status: "none" | "generating" | "active" | "failed"
  foda: Foda | null
  metas: string[]
}

export async function getFoda(): Promise<FodaOut> {
  const r = await api.get<FodaOut>("/onboarding/foda", { validateStatus: s => s === 200 || s === 404 })
  if (r.status === 404) return { status: "none", foda: null, metas: [] }
  return r.data
}
```

- [ ] **Step 2: Vista `frontend/src/app/dashboard/foda/page.tsx`**

```tsx
"use client"

import { useEffect, useRef, useState } from "react"
import { motion } from "framer-motion"
import { Loader2, TrendingUp, Compass, AlertTriangle, ShieldAlert } from "lucide-react"
import { Foda, FodaOut, getFoda } from "@/lib/foda"

type Quad = { key: keyof Foda; label: string; icon: typeof TrendingUp; accent: string; chip: string }
const QUADS: Quad[] = [
  { key: "fortalezas", label: "Fortalezas", icon: TrendingUp, accent: "border-t-green-500", chip: "text-green-700 bg-green-50" },
  { key: "oportunidades", label: "Oportunidades", icon: Compass, accent: "border-t-[var(--gob-navy)]", chip: "text-[var(--gob-navy)] bg-blue-50" },
  { key: "debilidades", label: "Debilidades", icon: AlertTriangle, accent: "border-t-amber-500", chip: "text-amber-700 bg-amber-50" },
  { key: "amenazas", label: "Amenazas", icon: ShieldAlert, accent: "border-t-red-500", chip: "text-red-700 bg-red-50" },
]

export default function FodaPage() {
  const [data, setData] = useState<FodaOut | null>(null)
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null)

  useEffect(() => {
    let alive = true
    const tick = async () => {
      try {
        const d = await getFoda()
        if (!alive) return
        setData(d)
        if (d.status === "generating") timer.current = setTimeout(tick, 4000)
      } catch { /* reintenta al recargar */ }
    }
    tick()
    return () => { alive = false; if (timer.current) clearTimeout(timer.current) }
  }, [])

  const f = data?.foda

  return (
    <div className="min-h-dvh bg-white text-black">
      <main className="max-w-5xl mx-auto px-[var(--px-fluid)] py-12 space-y-10">
        <div>
          <p className="text-xs font-medium tracking-widest text-gray-400 uppercase">Análisis estratégico</p>
          <h1 className="text-3xl font-bold tracking-tight">Matriz FODA</h1>
        </div>

        {(!data || data.status === "generating") && (
          <div className="border border-gray-100 rounded-2xl p-16 flex flex-col items-center justify-center gap-3 text-center">
            <Loader2 className="h-6 w-6 animate-spin text-gray-300" />
            <p className="text-sm text-gray-500">Todd está cruzando tu información interna y externa para armar la matriz…</p>
          </div>
        )}

        {data?.status === "failed" && (
          <div className="border border-gray-100 rounded-2xl p-12 text-center text-sm text-gray-500">
            No se pudo generar la matriz. Vuelve a confirmar tus metas para reintentar.
          </div>
        )}

        {data?.status === "active" && f && (
          <>
            {f.sintesis && (
              <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}
                className="bg-[var(--gob-navy)] text-[var(--gob-bone)] rounded-2xl p-6">
                <p className="text-[10px] font-medium tracking-widest uppercase opacity-70 mb-1.5">Síntesis</p>
                <p className="text-sm leading-relaxed">{f.sintesis}</p>
              </motion.div>
            )}

            <div className="grid gap-4 sm:grid-cols-2">
              {QUADS.map((q, i) => {
                const Icon = q.icon
                const items = (f[q.key] as string[]) || []
                return (
                  <motion.section key={q.key}
                    initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: 0.05 + i * 0.06 }}
                    className={`border border-gray-100 border-t-4 ${q.accent} rounded-2xl p-5`}>
                    <div className="flex items-center gap-2 mb-3">
                      <span className={`h-7 w-7 rounded-lg flex items-center justify-center ${q.chip}`}>
                        <Icon className="h-4 w-4" />
                      </span>
                      <h2 className="text-sm font-bold tracking-wide uppercase">{q.label}</h2>
                    </div>
                    {items.length > 0 ? (
                      <ul className="space-y-2">
                        {items.map((t, j) => (
                          <li key={j} className="text-sm text-gray-700 leading-snug flex gap-2">
                            <span className="text-gray-300">•</span><span>{t}</span>
                          </li>
                        ))}
                      </ul>
                    ) : <p className="text-xs text-gray-300 italic">Sin elementos.</p>}
                  </motion.section>
                )
              })}
            </div>

            {(f.metas_priorizadas?.length ?? 0) > 0 && (
              <section className="space-y-3 pt-2">
                <h2 className="text-xl font-bold tracking-tight">Tus prioridades</h2>
                <ol className="space-y-2">
                  {f.metas_priorizadas.map((m, i) => (
                    <li key={i} className="flex items-center gap-3 border border-gray-100 rounded-xl px-4 py-2.5">
                      <span className="w-6 h-6 rounded-full bg-[var(--gob-navy)] text-[var(--gob-bone)] text-xs font-bold flex items-center justify-center shrink-0">{i + 1}</span>
                      <span className="text-sm">{m}</span>
                    </li>
                  ))}
                </ol>
              </section>
            )}
          </>
        )}
      </main>
    </div>
  )
}
```

- [ ] **Step 3: Ítem en el sidebar**

En `frontend/src/components/ui/Sidebar.tsx`, agregar al import de `lucide-react` el ícono `Grid2x2` (o `LayoutGrid`), y al array `LINKS` (después de "Diagnóstico"):
```tsx
  { href: "/dashboard/foda", label: "FODA", exact: false, icon: LayoutGrid },
```
(Importar `LayoutGrid` de `lucide-react` en la lista de imports existente.)

- [ ] **Step 4: Redirect de la pantalla de metas**

En `frontend/src/app/onboarding/todd/metas/page.tsx`, en `confirmar`, cambiar `router.push("/dashboard/diagnostico")` por `router.push("/dashboard/foda")`.

- [ ] **Step 5: lint + build**

Run: `cd frontend && npm run lint` (por separado) y `cd frontend && npm run build`.
Expected: build exit 0; `lib/foda.ts`, `dashboard/foda/page.tsx`, `Sidebar.tsx`, `metas/page.tsx` sin errores nuevos (grep el output por `foda|metas|Sidebar`).

- [ ] **Step 6: Commit**

```bash
git add frontend/src/lib/foda.ts frontend/src/app/dashboard/foda/page.tsx frontend/src/components/ui/Sidebar.tsx frontend/src/app/onboarding/todd/metas/page.tsx
git commit -m "feat(todd-foda-fe): vista de la matriz FODA (2×2 premium) + sidebar + redirect"
```

---

## Self-Review (cobertura del spec, Plan B = Comp.4/5)

- **Generación FODA (Opus, sin web, síntesis interno+externo+metas)** → Task 1 (`generate_foda` + `_foda_fallback`). ✅
- **Disparo al confirmar metas** → Task 2 (`save_metas` setea `foda_status="generating"` + `.delay`). ✅
- **Persistencia en `content` (sin migración)** → Task 2 (`content["foda"]`, `["foda_status"]`). ✅
- **Vista propia 2×2 + metas** → Task 3 (`/dashboard/foda`, matriz on-brand) + sidebar + redirect. ✅
- **Fallback determinista** → Task 1 (`_foda_fallback`; sin key o error → no queda vacía). ✅
- **Calidad UX** → Task 3 (matriz 2×2 con acentos sobrios por cuadrante, síntesis destacada, carga elegante). ✅

Consistencia de tipos: `generate_foda(...) -> {fortalezas,oportunidades,debilidades,amenazas,sintesis,metas_priorizadas}` ↔ `foda_tasks` lo guarda en `content["foda"]` ↔ `GET /foda` lo devuelve en `FodaOut.foda` ↔ el front lo tipa `Foda` con esas mismas claves. `factores_externos`/`metas_orden` los dejó el Plan A en `content`. El `foda_status` ("none"|"generating"|"active"|"failed") guía el polling del front.

Puntos a verificar al implementar: que el bloque final de `save_metas` (Plan A) se reemplace correctamente (no duplicar el commit); que `LayoutGrid` exista en lucide-react (si no, usar `Grid2x2` o `Grid3x3`); que el worker en prod incluya la nueva task (`include`) — el redeploy del worker la registra; el FODA no necesita correr `alter_*` (no hay columnas nuevas).
