# Roadmap Estratégico — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Estructurar el plan a 3 años (que ya se genera tras el FODA) como un documento ejecutivo tipo Roadmap: encabezado (visión/misión/propuesta de valor/metas 3a/resúmenes FODA y entorno) + pilares estratégicos (3-5) + milestones por pilar×año, generado por IA como borrador editable, con vista + edición + PDF.

**Architecture:** Nueva columna `annual_plans.roadmap` (JSONB). Generador `app/services/ai/roadmap.py` (Opus tool-use, espejo de `foda.py`) que corre en la misma tarea Celery que el plan (`annual_plan_tasks._run_generation`) desde los datos existentes. Endpoints GET/PATCH para leer/editar + PDF. Frontend: 3ª opción "Roadmap" (por defecto) en `dashboard/plan/page.tsx`, editable por sección.

**Tech Stack:** FastAPI, SQLAlchemy async (Base/UUIDMixin/TimestampMixin, JSONB), Celery, Pydantic v2, anthropic SDK (tool use forzado), reportlab, Next.js 16 App Router, TypeScript, Tailwind v4, framer-motion, axios (`@/lib/api`, baseURL con `/api/v1`).

## Global Constraints

- Esquema de prod con scripts, **NO Alembic**: columna nueva vía `backend/scripts/alter_plan_roadmap.py` (`ALTER TABLE ... ADD COLUMN IF NOT EXISTS`), corrido en prod **solo con autorización humana**.
- Deploy: push a **AMBOS remotos** (`origin`=gobernia/gobernia web/Vercel, `cbeuvrin`=cbeuvrin/gobernia worker/Railway).
- Síntesis IA = `settings.DIAGNOSTICO_AI_MODEL` (Opus). Salida estructurada por tool use forzado (`tools=[TOOL]` + `tool_choice={"type":"tool","name":...}`, leer `block.input`).
- Sin API key → fallback determinista. **Nunca inventar el `target` numérico de las metas** (queda vacío para que el usuario lo fije).
- Rutas frontend sin doble `/api/v1` (baseURL de `@/lib/api` ya lo incluye).
- Suite backend: `cd backend && venv/bin/python -m pytest -q`. Lint frontend: `cd frontend && npx eslint <archivo>`.
- Forma canónica del roadmap (todas las tareas la comparten):
  ```json
  {"vision":"str","mision":"str","propuesta_valor":"str",
   "metas_3anios":[{"meta":"str","kpi":"str|null","valor_actual":"str|null","target":"str"}],
   "resumen_foda":"str","resumen_entorno":"str",
   "pilares":[{"nombre":"str","descripcion":"str","milestones":{"anio1":["str"],"anio2":["str"],"anio3":["str"]}}]}
  ```

---

### Task 1: Columna `roadmap` en AnnualPlan + script de alteración

**Files:**
- Modify: `backend/app/models/annual_plan.py` (añadir columna a `AnnualPlan`)
- Create: `backend/scripts/alter_plan_roadmap.py`
- Test: `backend/tests/unit/test_roadmap_model.py`

**Interfaces:**
- Produces: `AnnualPlan.roadmap` (JSONB, nullable).

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/unit/test_roadmap_model.py
from app.models.annual_plan import AnnualPlan


def test_annual_plan_tiene_columna_roadmap():
    assert "roadmap" in AnnualPlan.__table__.columns
    assert AnnualPlan.__table__.columns["roadmap"].nullable is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && venv/bin/python -m pytest tests/unit/test_roadmap_model.py -v`
Expected: FAIL (`assert 'roadmap' in ...` → KeyError/False).

- [ ] **Step 3: Write minimal implementation**

En `backend/app/models/annual_plan.py`, en la clase `AnnualPlan`, junto a la columna `milestones` (que ya es `Mapped[dict | None] = mapped_column(JSONB, nullable=True)`), añade:

```python
    roadmap: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
```

Crea `backend/scripts/alter_plan_roadmap.py`:

```python
"""Añade la columna annual_plans.roadmap SIN Alembic (prod aplica esquema con ALTER idempotente).
USO (solo con autorización humana — toca la DB):
    venv/bin/python -m scripts.alter_plan_roadmap
"""
import asyncio

from sqlalchemy import text

from app.db.session import engine


async def main():
    async with engine.begin() as conn:
        await conn.execute(text("ALTER TABLE annual_plans ADD COLUMN IF NOT EXISTS roadmap JSONB"))
    await engine.dispose()
    print("OK: columna annual_plans.roadmap")


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && venv/bin/python -m pytest tests/unit/test_roadmap_model.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/models/annual_plan.py backend/scripts/alter_plan_roadmap.py backend/tests/unit/test_roadmap_model.py
git commit -m "feat(roadmap): columna annual_plans.roadmap + script de alteración"
```

---

### Task 2: Generador del Roadmap (IA + fallback)

**Files:**
- Create: `backend/app/services/ai/roadmap.py`
- Test: `backend/tests/unit/test_roadmap_generator.py`

**Interfaces:**
- Consumes: `_create_with_retry` de `app.services.ai.agents.base`; `settings`.
- Produces: `roadmap.generate_roadmap(memory_buffer: dict, diagnostico_content: dict) -> dict` (forma canónica); `roadmap._roadmap_fallback(memory_buffer: dict, diagnostico_content: dict) -> dict`.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/unit/test_roadmap_generator.py
from app.services.ai.roadmap import generate_roadmap, _roadmap_fallback

_KEYS = {"vision", "mision", "propuesta_valor", "metas_3anios",
         "resumen_foda", "resumen_entorno", "pilares"}


def test_fallback_estructura_completa_y_metas_desde_kpis_sin_inventar_target():
    mb = {"vision": {"statement": "Ser referente en 3 años"},
          "kpis": {"financiero": [{"label": "Margen neto", "current_value": 6, "unit": "%"}]}}
    dcont = {"foda": {"sintesis": "Empresa sólida con retos de rentabilidad."}}
    r = _roadmap_fallback(mb, dcont)
    assert set(r.keys()) == _KEYS
    assert r["vision"] == "Ser referente en 3 años"
    assert r["resumen_foda"] == "Empresa sólida con retos de rentabilidad."
    m = r["metas_3anios"][0]
    assert m["kpi"] == "Margen neto" and m["valor_actual"] == "6%"
    assert m["target"] == ""  # NUNCA inventa el target


def test_fallback_sin_datos_no_truena():
    r = _roadmap_fallback({}, {})
    assert set(r.keys()) == _KEYS and r["pilares"] == [] and r["metas_3anios"] == []


def test_generate_roadmap_sin_api_key_usa_fallback(monkeypatch):
    monkeypatch.setattr("app.services.ai.roadmap.settings.ANTHROPIC_API_KEY", "")
    r = generate_roadmap({"vision": {"statement": "X"}}, {})
    assert r["vision"] == "X" and "pilares" in r
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && venv/bin/python -m pytest tests/unit/test_roadmap_generator.py -v`
Expected: FAIL (`ModuleNotFoundError: app.services.ai.roadmap`).

- [ ] **Step 3: Write minimal implementation**

```python
# backend/app/services/ai/roadmap.py
"""Genera el Roadmap Estratégico a 3 años (documento ejecutivo) desde los datos existentes.
Opus tool-use, sin web. Fallback determinista sin IA. NUNCA inventa el target numérico de las metas."""
import json

import anthropic

from app.core.config import settings
from app.services.ai.agents.base import _create_with_retry

_MILE = {"type": "object", "properties": {
    "anio1": {"type": "array", "items": {"type": "string"}},
    "anio2": {"type": "array", "items": {"type": "string"}},
    "anio3": {"type": "array", "items": {"type": "string"}},
}}

ROADMAP_TOOL = {
    "name": "roadmap_estrategico",
    "description": "Devuelve el roadmap estratégico a 3 años de la empresa.",
    "input_schema": {
        "type": "object",
        "properties": {
            "vision": {"type": "string"},
            "mision": {"type": "string"},
            "propuesta_valor": {"type": "string"},
            "metas_3anios": {"type": "array", "items": {"type": "object", "properties": {
                "meta": {"type": "string"},
                "kpi": {"type": "string"},
                "valor_actual": {"type": "string"},
                "target": {"type": "string", "description": "DÉJALO VACÍO: lo fija el dueño. No inventes."},
            }, "required": ["meta"]}},
            "resumen_foda": {"type": "string"},
            "resumen_entorno": {"type": "string"},
            "pilares": {"type": "array", "items": {"type": "object", "properties": {
                "nombre": {"type": "string"},
                "descripcion": {"type": "string"},
                "milestones": _MILE,
            }, "required": ["nombre", "descripcion"]}},
        },
        "required": ["vision", "mision", "propuesta_valor", "metas_3anios",
                     "resumen_foda", "resumen_entorno", "pilares"],
    },
}

_SYSTEM = (
    "Eres el consejo estratégico de Gobernia. Redacta el ROADMAP ESTRATÉGICO a 3 años de la empresa, "
    "en español, con lenguaje EJECUTIVO, claro e INSPIRADOR: es el documento que el dueño y sus "
    "directivos usarán para comunicación interna, gobernanza e inversión de recursos.\n"
    "- Deriva los PILARES estratégicos (3-5) del FODA y el diagnóstico (ej. Excelencia operacional, "
    "Expansión de mercado, Innovación). Cada pilar con una descripción breve y milestones TANGIBLES y "
    "MEDIBLES por año (2-4 por año).\n"
    "- Para 'metas_3anios' usa los KPIs reales: propón la meta y su 'kpi', pon 'valor_actual' si lo "
    "conoces, y deja 'target' VACÍO (el dueño lo fijará; NUNCA inventes el número).\n"
    "- 'resumen_foda' y 'resumen_entorno': síntesis ejecutiva breve.\n"
    "No inventes datos que no estén en la información dada."
)


def _kpis_metas(memory_buffer: dict) -> list[dict]:
    out = []
    for _cat, items in ((memory_buffer or {}).get("kpis") or {}).items():
        for k in (items or []):
            if not isinstance(k, dict):
                continue
            label = str(k.get("label") or "").strip()
            if not label:
                continue
            val = k.get("current_value")
            va = f"{val}{k.get('unit') or ''}" if val is not None else None
            out.append({"meta": f"Mejorar {label.lower()}", "kpi": label, "valor_actual": va, "target": ""})
    return out[:6]


def _roadmap_fallback(memory_buffer: dict, diagnostico_content: dict) -> dict:
    vision = str(((memory_buffer or {}).get("vision") or {}).get("statement") or "").strip()
    foda = (diagnostico_content or {}).get("foda") or {}
    return {
        "vision": vision,
        "mision": "",
        "propuesta_valor": "",
        "metas_3anios": _kpis_metas(memory_buffer),
        "resumen_foda": str(foda.get("sintesis") or "").strip(),
        "resumen_entorno": "",
        "pilares": [],
    }


def _norm_lista(v) -> list[str]:
    return [str(x).strip() for x in v if str(x).strip()] if isinstance(v, list) else []


def generate_roadmap(memory_buffer: dict, diagnostico_content: dict) -> dict:
    if not settings.ANTHROPIC_API_KEY:
        return _roadmap_fallback(memory_buffer, diagnostico_content)
    c = (memory_buffer or {}).get("company") or {}
    dcont = diagnostico_content or {}
    user = (
        f"EMPRESA: {json.dumps(c, ensure_ascii=False)[:1500]}\n"
        f"VISIÓN ACTUAL: {((memory_buffer or {}).get('vision') or {}).get('statement') or '(n/d)'}\n"
        f"KPIs: {json.dumps((memory_buffer or {}).get('kpis') or {}, ensure_ascii=False)[:1500]}\n"
        f"HALLAZGOS INTERNOS: {json.dumps(dcont.get('fortalezas_debilidades') or {}, ensure_ascii=False)[:2000]}\n"
        f"RIESGOS: {json.dumps(dcont.get('riesgos') or [], ensure_ascii=False)[:1200]}\n"
        f"FODA: {json.dumps(dcont.get('foda') or {}, ensure_ascii=False)[:2000]}\n"
        f"FACTORES EXTERNOS: {json.dumps(dcont.get('factores_externos') or {}, ensure_ascii=False)[:1500]}\n"
        f"METAS PRIORIZADAS: {json.dumps(dcont.get('metas_orden') or [], ensure_ascii=False)[:800]}\n\n"
        "Redacta el roadmap en el JSON indicado."
    )
    try:
        client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY, timeout=300.0)
        response = _create_with_retry(
            client, model=settings.DIAGNOSTICO_AI_MODEL, max_tokens=3072,
            system=_SYSTEM, messages=[{"role": "user", "content": user}],
            tools=[ROADMAP_TOOL], tool_choice={"type": "tool", "name": "roadmap_estrategico"},
        )
        block = next((b for b in response.content if getattr(b, "type", None) == "tool_use"), None)
        d = dict(block.input) if block and isinstance(block.input, dict) else {}
        if not d:
            return _roadmap_fallback(memory_buffer, diagnostico_content)
        metas = []
        for m in (d.get("metas_3anios") or []):
            if isinstance(m, dict) and str(m.get("meta") or "").strip():
                metas.append({"meta": str(m["meta"]).strip(), "kpi": (str(m.get("kpi")).strip() or None) if m.get("kpi") else None,
                              "valor_actual": (str(m.get("valor_actual")).strip() or None) if m.get("valor_actual") else None,
                              "target": str(m.get("target") or "").strip()})
        pilares = []
        for p in (d.get("pilares") or []):
            if not isinstance(p, dict) or not str(p.get("nombre") or "").strip():
                continue
            mi = p.get("milestones") or {}
            pilares.append({"nombre": str(p["nombre"]).strip(), "descripcion": str(p.get("descripcion") or "").strip(),
                            "milestones": {"anio1": _norm_lista(mi.get("anio1")),
                                           "anio2": _norm_lista(mi.get("anio2")),
                                           "anio3": _norm_lista(mi.get("anio3"))}})
        return {
            "vision": str(d.get("vision") or "").strip(),
            "mision": str(d.get("mision") or "").strip(),
            "propuesta_valor": str(d.get("propuesta_valor") or "").strip(),
            "metas_3anios": metas,
            "resumen_foda": str(d.get("resumen_foda") or "").strip(),
            "resumen_entorno": str(d.get("resumen_entorno") or "").strip(),
            "pilares": pilares,
        }
    except Exception:
        return _roadmap_fallback(memory_buffer, diagnostico_content)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && venv/bin/python -m pytest tests/unit/test_roadmap_generator.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/ai/roadmap.py backend/tests/unit/test_roadmap_generator.py
git commit -m "feat(roadmap): generador IA + fallback (no inventa targets)"
```

---

### Task 3: Wire-up en la generación del plan + endpoints GET/PATCH

**Files:**
- Modify: `backend/app/tasks/annual_plan_tasks.py` (en `_run_generation`, poblar `plan.roadmap`)
- Modify: `backend/app/api/v1/annual_plan/router.py` (endpoints + imports)
- Test: `backend/tests/integration/test_roadmap_api.py`

**Interfaces:**
- Consumes: `generate_roadmap` (Task 2), `_current_plan` (helper existente en el router), `AnnualPlan`.
- Produces: `GET /annual-plan/roadmap`, `PATCH /annual-plan/roadmap`.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/integration/test_roadmap_api.py
import pytest
from unittest.mock import AsyncMock, MagicMock
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.core.dependencies import get_current_user_id, get_db


def _user():
    return "user-123"


def _db_override(db):
    async def _dep():
        yield db
    return _dep


@pytest.mark.asyncio
async def test_get_roadmap_sin_plan_da_404():
    db = AsyncMock()
    res = MagicMock(); res.scalar_one_or_none.return_value = None
    db.execute = AsyncMock(return_value=res)
    app.dependency_overrides[get_db] = _db_override(db)
    app.dependency_overrides[get_current_user_id] = _user
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.get("/api/v1/annual-plan/roadmap")
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_patch_roadmap_guarda_y_devuelve():
    plan = MagicMock(); plan.roadmap = {}
    res = MagicMock(); res.scalar_one_or_none.return_value = plan
    db = AsyncMock(); db.execute = AsyncMock(return_value=res); db.commit = AsyncMock()
    app.dependency_overrides[get_db] = _db_override(db)
    app.dependency_overrides[get_current_user_id] = _user
    body = {"vision": "Nueva visión", "pilares": []}
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.patch("/api/v1/annual-plan/roadmap", json=body)
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 200
    assert r.json()["vision"] == "Nueva visión"
    assert plan.roadmap["vision"] == "Nueva visión"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && venv/bin/python -m pytest tests/integration/test_roadmap_api.py -v`
Expected: FAIL (rutas 404 inexistentes).

- [ ] **Step 3: Write minimal implementation**

En `backend/app/api/v1/annual_plan/router.py`, confirma que existan estos imports (añade los que falten, junto a los demás del archivo): `from fastapi import Body`, `from sqlalchemy.orm.attributes import flag_modified`, `from app.models.annual_plan import AnnualPlan`. Verifica que exista el helper `_current_plan(user_id, db)` (se usa en `generate_plan`); si no, úsalo tal cual está definido en el archivo. Añade:

```python
@router.get("/annual-plan/roadmap")
async def get_roadmap(
    user_id: str = Depends(get_current_user_id), db: AsyncSession = Depends(get_db),
):
    plan = await _current_plan(user_id, db)
    if plan is None:
        raise HTTPException(status_code=404, detail="No hay plan generado.")
    return plan.roadmap or {}


@router.patch("/annual-plan/roadmap")
async def patch_roadmap(
    body: dict = Body(...),
    user_id: str = Depends(get_current_user_id), db: AsyncSession = Depends(get_db),
):
    plan = await _current_plan(user_id, db)
    if plan is None:
        raise HTTPException(status_code=404, detail="No hay plan generado.")
    plan.roadmap = body
    flag_modified(plan, "roadmap")
    await db.commit()
    return plan.roadmap
```

En `backend/app/tasks/annual_plan_tasks.py`, dentro de `_run_generation`, DESPUÉS de que el plan (meses/objetivos/tareas) ya está construido y ANTES del `await db.commit()` final del bloque `try`, añade la generación del roadmap (usa el `memory_buffer` y el `dcont` que ya están en scope):

```python
        from app.services.ai.roadmap import generate_roadmap
        try:
            plan.roadmap = await asyncio.to_thread(generate_roadmap, memory_buffer, dcont)
        except Exception:
            plan.roadmap = None
```

(Si `asyncio` no está importado en el archivo, usa el patrón de import ya presente para las llamadas de IA; el resto de generadores del archivo ya corren en hilo. Confirma con `grep -n "import asyncio\|to_thread" backend/app/tasks/annual_plan_tasks.py`.)

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && venv/bin/python -m pytest tests/integration/test_roadmap_api.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Run full suite + commit**

Run: `cd backend && venv/bin/python -m pytest -q` → all passed.

```bash
git add backend/app/api/v1/annual_plan/router.py backend/app/tasks/annual_plan_tasks.py backend/tests/integration/test_roadmap_api.py
git commit -m "feat(roadmap): genera roadmap con el plan + endpoints GET/PATCH"
```

---

### Task 4: PDF del Roadmap

**Files:**
- Create: `backend/app/services/pdf/roadmap_pdf.py`
- Modify: `backend/app/api/v1/annual_plan/router.py` (endpoint `/annual-plan/roadmap/pdf`)
- Test: `backend/tests/unit/test_roadmap_pdf.py`

**Interfaces:**
- Consumes: `AnnualPlan.roadmap` (Task 1), `_current_plan`.
- Produces: `build_roadmap_pdf(roadmap: dict, company_name: str | None) -> bytes`; `GET /annual-plan/roadmap/pdf`.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/unit/test_roadmap_pdf.py
from app.services.pdf.roadmap_pdf import build_roadmap_pdf


def test_pdf_roadmap_completo_es_valido():
    roadmap = {
        "vision": "Ser referente", "mision": "Crear valor", "propuesta_valor": "Calidad y cercanía",
        "metas_3anios": [{"meta": "Mejorar margen", "kpi": "Margen", "valor_actual": "6%", "target": "12%"}],
        "resumen_foda": "Sólida.", "resumen_entorno": "Mercado en crecimiento.",
        "pilares": [{"nombre": "Excelencia operacional", "descripcion": "Procesos.",
                     "milestones": {"anio1": ["Mapear procesos"], "anio2": ["Certificar"], "anio3": ["Automatizar 50%"]}}],
    }
    pdf = build_roadmap_pdf(roadmap, "Keting Media")
    assert pdf[:5] == b"%PDF-" and len(pdf) > 1000


def test_pdf_roadmap_vacio_no_truena():
    assert build_roadmap_pdf({}, None)[:5] == b"%PDF-"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && venv/bin/python -m pytest tests/unit/test_roadmap_pdf.py -v`
Expected: FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: Write minimal implementation**

```python
# backend/app/services/pdf/roadmap_pdf.py
from io import BytesIO
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer


def build_roadmap_pdf(roadmap: dict, company_name: str | None) -> bytes:
    roadmap = roadmap or {}
    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=letter,
                            topMargin=2 * cm, bottomMargin=2 * cm, leftMargin=2 * cm, rightMargin=2 * cm)
    base = getSampleStyleSheet()
    h1 = ParagraphStyle("h1", parent=base["Title"], fontSize=20, spaceAfter=6)
    h2 = ParagraphStyle("h2", parent=base["Heading2"], fontSize=13, spaceBefore=14, spaceAfter=4)
    h3 = ParagraphStyle("h3", parent=base["Heading3"], fontSize=11, spaceBefore=8, spaceAfter=2,
                        textColor=colors.HexColor("#1e3a5f"))
    body = ParagraphStyle("body", parent=base["BodyText"], fontSize=10.5, leading=15)
    item = ParagraphStyle("item", parent=base["BodyText"], fontSize=10, leading=14, spaceAfter=2)
    label = ParagraphStyle("label", parent=base["BodyText"], fontSize=8, leading=11,
                           textColor=colors.HexColor("#888888"), spaceAfter=1)

    story = [Paragraph(escape(f"Roadmap estratégico — {company_name or 'tu empresa'}"), h1), Spacer(1, 0.2 * cm)]

    def _txt(title, val):
        if str(val or "").strip():
            story.append(Paragraph(title, h3))
            story.append(Paragraph(escape(str(val).strip()), body))

    _txt("Visión", roadmap.get("vision"))
    _txt("Misión", roadmap.get("mision"))
    _txt("Propuesta de valor", roadmap.get("propuesta_valor"))

    metas = roadmap.get("metas_3anios") or []
    if metas:
        story.append(Paragraph("Metas a 3 años", h2))
        for m in metas:
            if not isinstance(m, dict) or not str(m.get("meta") or "").strip():
                continue
            base_txt = f' <font size=8 color="#888888">(hoy: {escape(str(m.get("valor_actual")))}' \
                       f'{" · meta: " + escape(str(m.get("target"))) if str(m.get("target") or "").strip() else ""})</font>' \
                       if str(m.get("valor_actual") or "").strip() or str(m.get("target") or "").strip() else ""
            story.append(Paragraph(f'● {escape(str(m["meta"]).strip())}{base_txt}', item))

    _txt("Resumen FODA", roadmap.get("resumen_foda"))
    _txt("Resumen del entorno", roadmap.get("resumen_entorno"))

    pilares = roadmap.get("pilares") or []
    if pilares:
        story.append(Paragraph("Pilares estratégicos", h2))
        for p in pilares:
            if not isinstance(p, dict) or not str(p.get("nombre") or "").strip():
                continue
            story.append(Paragraph(escape(str(p["nombre"]).strip()), h3))
            if str(p.get("descripcion") or "").strip():
                story.append(Paragraph(escape(str(p["descripcion"]).strip()), body))
            mi = p.get("milestones") or {}
            for anio, key in (("Año 1", "anio1"), ("Año 2", "anio2"), ("Año 3", "anio3")):
                items = [str(x).strip() for x in (mi.get(key) or []) if str(x).strip()]
                if items:
                    story.append(Paragraph(anio.upper(), label))
                    for it in items:
                        story.append(Paragraph(f"● {escape(it)}", item))

    doc.build(story)
    return buf.getvalue()
```

En `backend/app/api/v1/annual_plan/router.py` añade (necesita `import anyio` y `from fastapi import Response`; confirma que estén, y un helper de nombre de empresa — reusa el patrón de `OnboardingSession.memory_buffer["company"]["name"]` ya usado en el archivo, o cárgalo con un `select(OnboardingSession)` como en otros endpoints):

```python
@router.get("/annual-plan/roadmap/pdf")
async def roadmap_pdf(
    user_id: str = Depends(get_current_user_id), db: AsyncSession = Depends(get_db),
):
    plan = await _current_plan(user_id, db)
    if plan is None or not plan.roadmap:
        raise HTTPException(status_code=404, detail="No hay roadmap disponible.")
    onb = (await db.execute(
        select(OnboardingSession).where(OnboardingSession.user_id == user_id)
        .order_by(OnboardingSession.created_at.desc())
    )).scalars().first()
    company_name = (((onb.memory_buffer if onb else {}) or {}).get("company") or {}).get("name")
    from app.services.pdf.roadmap_pdf import build_roadmap_pdf
    pdf = await anyio.to_thread.run_sync(lambda: build_roadmap_pdf(plan.roadmap, company_name))
    return Response(content=pdf, media_type="application/pdf",
                    headers={"Content-Disposition": 'attachment; filename="roadmap.pdf"'})
```

(Confirma que `OnboardingSession` y `select` estén importados en el archivo; añádelos si no.)

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && venv/bin/python -m pytest tests/unit/test_roadmap_pdf.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/pdf/roadmap_pdf.py backend/app/api/v1/annual_plan/router.py backend/tests/unit/test_roadmap_pdf.py
git commit -m "feat(roadmap): PDF del roadmap + endpoint"
```

---

### Task 5: Frontend — librería del Roadmap

**Files:**
- Create: `frontend/src/lib/roadmap.ts`

**Interfaces:**
- Consumes: `@/lib/api`.
- Produces: tipos `Meta3a`, `Pilar`, `Roadmap`; funciones `getRoadmap`, `saveRoadmap`, `downloadRoadmapPdf`.

- [ ] **Step 1: Write the implementation**

```typescript
// frontend/src/lib/roadmap.ts
import api from "@/lib/api"

export interface Meta3a { meta: string; kpi: string | null; valor_actual: string | null; target: string }
export interface Pilar {
  nombre: string; descripcion: string
  milestones: { anio1: string[]; anio2: string[]; anio3: string[] }
}
export interface Roadmap {
  vision: string; mision: string; propuesta_valor: string
  metas_3anios: Meta3a[]; resumen_foda: string; resumen_entorno: string; pilares: Pilar[]
}

const EMPTY: Roadmap = {
  vision: "", mision: "", propuesta_valor: "", metas_3anios: [],
  resumen_foda: "", resumen_entorno: "", pilares: [],
}

export async function getRoadmap(): Promise<Roadmap> {
  const r = await api.get<Partial<Roadmap>>("/annual-plan/roadmap")
  return { ...EMPTY, ...(r.data || {}) }
}

export async function saveRoadmap(roadmap: Roadmap): Promise<Roadmap> {
  const r = await api.patch<Roadmap>("/annual-plan/roadmap", roadmap)
  return { ...EMPTY, ...(r.data || {}) }
}

export async function downloadRoadmapPdf(): Promise<void> {
  const r = await api.get("/annual-plan/roadmap/pdf", { responseType: "blob" })
  const url = URL.createObjectURL(r.data as Blob)
  const a = document.createElement("a")
  a.href = url; a.download = "roadmap.pdf"
  document.body.appendChild(a); a.click(); a.remove()
  URL.revokeObjectURL(url)
}
```

- [ ] **Step 2: Lint**

Run: `cd frontend && npx eslint src/lib/roadmap.ts`
Expected: sin errores.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/lib/roadmap.ts
git commit -m "feat(roadmap-fe): librería de API"
```

---

### Task 6: Frontend — vista Roadmap (por defecto) + edición por sección + PDF

**Files:**
- Modify: `frontend/src/app/dashboard/plan/page.tsx`

**Interfaces:**
- Consumes: `@/lib/roadmap` (Task 5).

- [ ] **Step 1: Implement the Roadmap view**

En `frontend/src/app/dashboard/plan/page.tsx`:
1. El toggle actual `["camino","timeline"]` pasa a `["roadmap","camino","timeline"]`, con **"roadmap" como valor inicial** de `view`. Etiquetas: "Roadmap" / "Vista Camino" / "Vista Timeline".
2. Cuando `view === "roadmap"`: carga el roadmap con `getRoadmap()` (una vez, al entrar a esa vista o al montar si el plan está `active`), estado `roadmap: Roadmap | null` + `loadingRoadmap`. Guarda con `saveRoadmap`.
3. **Render del documento ejecutivo** (estilo de marca, tokens `--gob-*`, tarjetas `rounded-2xl border border-gray-100`, buena jerarquía y espaciado — inspírate en `dashboard/diagnostico/page.tsx` y `dashboard/foda/page.tsx`):
   - Header sticky con título "Roadmap estratégico" + botón **PDF** (`downloadRoadmapPdf`).
   - **Encabezado ejecutivo:** bloques Visión, Misión, Propuesta de valor (párrafos), **Metas a 3 años** (lista: cada meta con su `kpi`, `valor_actual` como "hoy" y un input para `target`), **Resumen FODA**, **Resumen del entorno**.
   - **Pilares estratégicos:** una tarjeta por pilar con `nombre` + `descripcion` + una mini-tabla de milestones **Año 1 / Año 2 / Año 3** (3 columnas, listas).
4. **Edición por sección:** cada bloque tiene un botón "Editar" que convierte sus textos en `<textarea>`/`<input>` (para pilares/milestones: editar nombre, descripción y las tres listas separadas por saltos de línea). "Guardar" arma el objeto `Roadmap` completo (fusionando el bloque editado con el resto) y llama `saveRoadmap(next)`, actualizando el estado. "Cancelar" descarta. Mantén simple: un solo bloque en edición a la vez (`editing: string | null`).
5. Estados: si `getRoadmap` devuelve todo vacío (plan recién generado sin roadmap, o generándose), muestra un aviso "Tu roadmap se está preparando…" o "Aún no hay roadmap; regenera tu plan". El Camino/Timeline siguen igual bajo sus toggles.

Sigue el patrón de `dashboard/foda/page.tsx` para el header sticky + PDF, y de `dashboard/diagnostico/page.tsx` para bloques/tarjetas.

- [ ] **Step 2: Lint**

Run: `cd frontend && npx eslint src/app/dashboard/plan/page.tsx`
Expected: sin errores. Si el efecto de carga dispara `react-hooks/set-state-in-effect`, usa `// eslint-disable-next-line react-hooks/set-state-in-effect` (convención del repo). Guarda con guard de desmontaje (`aliveRef`) si añades polling.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/app/dashboard/plan/page.tsx
git commit -m "feat(roadmap-fe): vista Roadmap por defecto + edición por sección + PDF"
```

---

## Despliegue (tras completar, con autorización del usuario)
1. `cd backend && venv/bin/python -m pytest -q` → verde.
2. Prod (con autorización): `venv/bin/python -m scripts.alter_plan_roadmap`.
3. Push a **ambos remotos**: `git push origin main && git push cbeuvrin main`.
4. Verificar redeploy de Vercel (web) y Railway (worker). El roadmap solo aparece en planes **nuevos** (regenerar).

## Self-Review (autor)
- **Cobertura del spec:** columna+alter (T1) ✓; generador IA+fallback sin inventar targets (T2) ✓; wire-up en generación + GET/PATCH (T3) ✓; PDF (T4) ✓; lib FE (T5) ✓; vista Roadmap por defecto + edición por sección + PDF (T6) ✓. Camino/Timeline intactos como ejecución. Metas desde KPIs, target editable. Pilares 3-5 + milestones por pilar×año.
- **Consistencia de tipos:** `generate_roadmap(memory_buffer, diagnostico_content) -> dict` (forma canónica) usado en T3 wire-up; `_current_plan(user_id, db)` reusado; forma del roadmap idéntica en modelo (JSONB), generador, PDF, `lib/roadmap.ts` (`Roadmap`), endpoints. Rutas FE sin doble `/api/v1`.
- **Placeholders:** T1–T5 con código completo; T6 es UI descriptiva apoyada en páginas de referencia citadas y los tipos exactos de T5.
