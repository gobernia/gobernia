# Fase 2 (Backend) — Diagnóstico estratégico con investigación web — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Construir el backend del Diagnóstico estratégico: campos semilla en onboarding, modelo + migración, motor de IA con web search (Opus 4.8), task de Celery, compuerta de datos, API y PDF — todo testeable con pytest.

**Architecture:** Patrón asíncrono idéntico al plan de 12 meses. Endpoint `POST /diagnostico/generate` valida datos (compuerta), crea una fila `DiagnosticoEstrategico` en `generating`, encola una task de Celery que usa `task_session()`, llama a Claude Opus 4.8 con la herramienta `web_search`, parsea JSON de 6 secciones + fuentes, y persiste `active`/`failed`. Endpoints de status/get/pdf para el frontend (plan aparte).

**Tech Stack:** FastAPI, SQLAlchemy async (`app.models.base`: Base/UUIDMixin/TimestampMixin), Alembic (`app/db/migrations/versions/`), Celery (`app.tasks.worker.celery_app`, `task_session()`), Pydantic v2, anthropic SDK (`_create_with_retry`, `_extract_json_object` de `app/services/ai/agents/base.py`), reportlab. Modelo IA `settings.DIAGNOSTICO_AI_MODEL` (`claude-opus-4-8`).

**Verificación:** Backend tiene pytest (asyncio, DB mockeada con `AsyncMock` + `dependency_overrides`). Comandos desde `backend/` con el venv: `./venv/bin/pytest`. La lógica pura (parseo, prompt, compuerta) se testea sin red ni DB; los endpoints/task mockean la IA y la DB.

> **Decisión de deploy-safety:** `website`/`competitors` van **opcionales en `Etapa1Input`** (no rompe el submit de Etapa 1 si el backend despliega antes que el form del frontend); la **obligatoriedad la impone `missing_diagnostico_data`** al generar el diagnóstico. El form del frontend (plan aparte) los marca requeridos en la UI.

---

### Task 1: Config + campos semilla en onboarding (web + competidores)

**Files:**
- Modify: `backend/app/core/config.py`
- Modify: `backend/app/schemas/etapa1.py`
- Modify: `backend/app/services/ai/memory_buffer.py`
- Test: `backend/tests/unit/test_etapa1_seed_fields.py` (crear)

- [ ] **Step 1: Test de los campos nuevos + mapeo a memory_buffer**

Crear `backend/tests/unit/test_etapa1_seed_fields.py`:

```python
from app.schemas.etapa1 import Etapa1Input
from app.schemas.enums import IndustryType, YearsOperating, EmployeeRange, RevenueRange, BranchCount, BoardStatus
from app.services.ai.memory_buffer import build_etapa1_memory


def _base(**over):
    data = dict(
        company_name="ACME", industry=IndustryType.other, industry_custom="Software",
        location_city="CDMX", location_state="CDMX", location_country="México",
        years_operating=YearsOperating.y1_3, employees=EmployeeRange.e11_50,
        annual_revenue=RevenueRange.r1_10m, branches=BranchCount.b1,
        is_family_business=False, has_board=BoardStatus.no,
    )
    data.update(over)
    return Etapa1Input(**data)


def test_website_and_competitors_optional_default():
    inp = _base()
    assert inp.website is None
    assert inp.competitors == []


def test_website_and_competitors_accepted():
    inp = _base(website="https://acme.com", competitors=["Globex", "Initech"])
    assert inp.website == "https://acme.com"
    assert inp.competitors == ["Globex", "Initech"]


def test_competitors_capped_and_trimmed():
    inp = _base(competitors=[" A ", "", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K"])
    # vacíos descartados, recortados, máximo 10
    assert "" not in inp.competitors
    assert inp.competitors[0] == "A"
    assert len(inp.competitors) <= 10


def test_memory_buffer_includes_seed_fields():
    mb = build_etapa1_memory(_base(website="https://acme.com", competitors=["Globex"]), [])
    assert mb["company"]["website"] == "https://acme.com"
    assert mb["company"]["competitors"] == ["Globex"]
```

- [ ] **Step 2: Correr el test (falla)**

Run: `cd backend && ./venv/bin/pytest tests/unit/test_etapa1_seed_fields.py -q`
Expected: FAIL (campos no existen aún).

- [ ] **Step 3: Agregar `DIAGNOSTICO_AI_MODEL` en `config.py`**

En la clase `Settings` de `backend/app/core/config.py`, junto a `AI_MODEL`:

```python
    DIAGNOSTICO_AI_MODEL: str = "claude-opus-4-8"
```

- [ ] **Step 4: Agregar los campos a `Etapa1Input`**

En `backend/app/schemas/etapa1.py`, dentro de `Etapa1Input` (al final de los campos, antes de los validators), agregar y normalizar:

```python
    # Bloque 4 — Datos para investigación (opcionales en el schema; obligatorios al generar diagnóstico)
    website: str | None = Field(default=None, max_length=300)
    competitors: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def normalize_seed_fields(self) -> "Etapa1Input":
        if self.website is not None:
            self.website = self.website.strip() or None
        self.competitors = [c.strip() for c in self.competitors if c and c.strip()][:10]
        return self
```

(`Field` y `model_validator` ya están importados en el archivo.)

- [ ] **Step 5: Mapear a `memory_buffer["company"]`**

En `backend/app/services/ai/memory_buffer.py`, dentro de `build_etapa1_memory`, en el dict `"company"`, después de `"has_board": data.has_board.value,` agregar:

```python
            "website": data.website,
            "competitors": data.competitors,
```

- [ ] **Step 6: Correr el test (pasa)**

Run: `cd backend && ./venv/bin/pytest tests/unit/test_etapa1_seed_fields.py -q`
Expected: PASS (4 tests).

- [ ] **Step 7: Commit**

```bash
git add backend/app/core/config.py backend/app/schemas/etapa1.py backend/app/services/ai/memory_buffer.py backend/tests/unit/test_etapa1_seed_fields.py
git commit -m "feat(fase2): campos semilla web+competidores en onboarding + config DIAGNOSTICO_AI_MODEL"
```

---

### Task 2: Compuerta de datos del diagnóstico

**Files:**
- Modify: `backend/app/services/data_completeness.py`
- Test: `backend/tests/unit/test_diagnostico_completeness.py` (crear)

- [ ] **Step 1: Test de `missing_diagnostico_data`**

Crear `backend/tests/unit/test_diagnostico_completeness.py`:

```python
from app.services.data_completeness import missing_diagnostico_data

OK = {"company": {"name": "ACME", "website": "https://acme.com", "competitors": ["Globex"]}}


def test_completo():
    assert missing_diagnostico_data(OK) == []


def test_sin_nombre():
    out = missing_diagnostico_data({"company": {"website": "https://a.com", "competitors": ["X"]}})
    assert out == ["el perfil de tu empresa (etapa 1)"]


def test_sin_web():
    out = missing_diagnostico_data({"company": {"name": "ACME", "competitors": ["X"]}})
    assert out == ["la página web de tu empresa (etapa 1)"]


def test_sin_competidores():
    out = missing_diagnostico_data({"company": {"name": "ACME", "website": "https://a.com", "competitors": []}})
    assert out == ["al menos un competidor (etapa 1)"]


def test_buffer_none():
    assert len(missing_diagnostico_data(None)) == 3
```

- [ ] **Step 2: Correr (falla)**

Run: `cd backend && ./venv/bin/pytest tests/unit/test_diagnostico_completeness.py -q`
Expected: FAIL (`missing_diagnostico_data` no existe).

- [ ] **Step 3: Implementar `missing_diagnostico_data`**

Al final de `backend/app/services/data_completeness.py`:

```python
def missing_diagnostico_data(memory_buffer: dict | None) -> list[str]:
    """Faltantes para generar el diagnóstico estratégico (no requiere KPIs)."""
    company = (memory_buffer or {}).get("company") or {}
    faltantes: list[str] = []
    if not company.get("name"):
        faltantes.append("el perfil de tu empresa (etapa 1)")
    if not (company.get("website") or "").strip():
        faltantes.append("la página web de tu empresa (etapa 1)")
    if not [c for c in (company.get("competitors") or []) if c and str(c).strip()]:
        faltantes.append("al menos un competidor (etapa 1)")
    return faltantes
```

- [ ] **Step 4: Correr (pasa)**

Run: `cd backend && ./venv/bin/pytest tests/unit/test_diagnostico_completeness.py -q`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/data_completeness.py backend/tests/unit/test_diagnostico_completeness.py
git commit -m "feat(fase2): compuerta missing_diagnostico_data (web+competidores)"
```

---

### Task 3: Modelo `DiagnosticoEstrategico` + migración

**Files:**
- Create: `backend/app/models/diagnostico_estrategico.py`
- Modify: `backend/app/models/__init__.py` (registrar el modelo para Alembic/metadata)
- Create: `backend/app/db/migrations/versions/004_diagnostico.py`

- [ ] **Step 1: Crear el modelo**

`backend/app/models/diagnostico_estrategico.py`:

```python
from sqlalchemy import String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin


class DiagnosticoEstrategico(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "diagnosticos_estrategicos"

    user_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="generating")
    content: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    fail_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
```

- [ ] **Step 2: Registrar el modelo**

Leer `backend/app/models/__init__.py`. Si importa los modelos (p. ej. `from app.models.annual_plan import AnnualPlan`), agregar:

```python
from app.models.diagnostico_estrategico import DiagnosticoEstrategico  # noqa: F401
```

(Para que `Base.metadata` lo conozca y Alembic/los tests lo vean. Si el archivo está vacío o no sigue ese patrón, igualmente agregar el import.)

- [ ] **Step 3: Crear la migración**

`backend/app/db/migrations/versions/004_diagnostico.py`:

```python
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "004_diagnostico"
down_revision = "003_annual_plan"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "diagnosticos_estrategicos",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", sa.String, nullable=False, index=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="generating"),
        sa.Column("content", postgresql.JSONB, nullable=True),
        sa.Column("fail_reason", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("diagnosticos_estrategicos")
```

Verificar que `003_annual_plan` es la cabeza actual: `cd backend && ./venv/bin/alembic heads` debe mostrar `003_annual_plan`. Si la cabeza fuera otra, ajustar `down_revision`.

- [ ] **Step 4: Verificar que la migración carga (sin aplicarla a prod todavía)**

Run: `cd backend && ./venv/bin/alembic history | head` y `./venv/bin/python -c "import app.db.migrations.versions.004_diagnostico"` (debe importar sin error).
Expected: la migración aparece en el history como `004_diagnostico -> 003_annual_plan`. (La aplicación real `alembic upgrade head` contra la DB se hace en el despliegue / paso de integración, no aquí — es no destructiva: solo crea una tabla.)

- [ ] **Step 5: Commit**

```bash
git add backend/app/models/diagnostico_estrategico.py backend/app/models/__init__.py backend/app/db/migrations/versions/004_diagnostico.py
git commit -m "feat(fase2): modelo DiagnosticoEstrategico + migración 004"
```

---

### Task 4: Motor de diagnóstico (IA con web search)

**Files:**
- Create: `backend/app/services/ai/diagnostico_estrategico.py`
- Test: `backend/tests/unit/test_diagnostico_engine.py` (crear)

Las 6 secciones tienen estas keys fijas: `resumen_ejecutivo`, `presencia_digital`, `competencia`, `tendencias_mercado`, `contexto_economico`, `conclusiones`.

- [ ] **Step 1: Tests de la lógica pura (`build_prompt`, `parse_diagnostico`)**

Crear `backend/tests/unit/test_diagnostico_engine.py`:

```python
import json
from app.services.ai.diagnostico_estrategico import (
    build_prompt, parse_diagnostico, SECTION_KEYS, _diagnostico_vacio,
)

MB = {"company": {
    "name": "ACME", "industry": "software",
    "location": {"city": "CDMX", "state": "CDMX", "country": "México"},
    "website": "https://acme.com", "competitors": ["Globex", "Initech"],
}}


def test_build_prompt_incluye_semillas():
    p = build_prompt(MB)
    assert "ACME" in p and "acme.com" in p and "Globex" in p and "México" in p


def test_parse_completo():
    payload = {
        "sections": {k: f"cuerpo {k}" for k in SECTION_KEYS},
        "sources": [{"title": "Fuente", "url": "https://x.com"}],
    }
    content = parse_diagnostico(json.dumps(payload))
    assert [s["key"] for s in content["sections"]] == list(SECTION_KEYS)
    assert content["sources"][0]["url"] == "https://x.com"
    assert not _diagnostico_vacio(content)


def test_parse_basura_es_vacio():
    content = parse_diagnostico("no soy json")
    assert _diagnostico_vacio(content)


def test_parse_parcial_rellena_y_marca_vacio_si_faltan_todas():
    content = parse_diagnostico(json.dumps({"sections": {}, "sources": []}))
    # 6 secciones presentes pero con cuerpo vacío → se considera vacío
    assert len(content["sections"]) == len(SECTION_KEYS)
    assert _diagnostico_vacio(content)
```

- [ ] **Step 2: Correr (falla)**

Run: `cd backend && ./venv/bin/pytest tests/unit/test_diagnostico_engine.py -q`
Expected: FAIL (módulo no existe).

- [ ] **Step 3: Implementar el motor**

`backend/app/services/ai/diagnostico_estrategico.py`:

```python
"""Motor del Diagnóstico estratégico con investigación web (Claude + web_search).

Lógica pura (prompt, parseo, validación) separada de la llamada de red para testear sin
red ni DB. La generación corre en una task de Celery (app.tasks.diagnostico_tasks).
"""
import json

import anthropic

from app.core.config import settings
from app.services.ai.agents.base import _create_with_retry, _extract_json_object

SECTION_KEYS = (
    "resumen_ejecutivo",
    "presencia_digital",
    "competencia",
    "tendencias_mercado",
    "contexto_economico",
    "conclusiones",
)
SECTION_TITLES = {
    "resumen_ejecutivo": "Resumen ejecutivo",
    "presencia_digital": "Presencia digital",
    "competencia": "Competencia: percibida vs. real",
    "tendencias_mercado": "Tendencias de mercado",
    "contexto_economico": "Contexto económico y regulatorio",
    "conclusiones": "Conclusiones y recomendaciones",
}

_MAX_CONTINUATIONS = 6  # tope de reanudaciones por pause_turn
_MAX_SEARCHES = 6       # guardrail de costo del web search

SYSTEM_PROMPT = """Eres un analista estratégico senior del consejo de Gobernia.
Investigas en la web la realidad de una empresa y produces un diagnóstico estratégico
profesional, específico y accionable, en español.

Usa la herramienta de búsqueda web para investigar de verdad: el sitio de la empresa,
su presencia digital, sus competidores reales en su región y segmento, tendencias de su
industria y contexto económico/regulatorio de su país/región.

CRÍTICO — Competencia percibida vs. real: el usuario te dará la lista de competidores que
ÉL CREE tener. Contrástala con lo que encuentres: coincidencias, competidores reales que el
usuario omitió, y supuestos competidores que ya no lo son. Ese contraste es la sección más
valiosa.

Responde ÚNICAMENTE con un objeto JSON válido con esta forma exacta (sin texto fuera del JSON):
{
  "sections": {
    "resumen_ejecutivo": "string",
    "presencia_digital": "string",
    "competencia": "string",
    "tendencias_mercado": "string",
    "contexto_economico": "string",
    "conclusiones": "string"
  },
  "sources": [{"title": "string", "url": "string"}]
}
Cada sección: 2-4 párrafos, concreta y basada en lo que encontraste. 'sources' = las páginas
reales que consultaste."""


def build_prompt(memory_buffer: dict) -> str:
    c = (memory_buffer or {}).get("company", {}) or {}
    loc = c.get("location", {}) or {}
    region = ", ".join(x for x in [loc.get("city"), loc.get("state"), loc.get("country")] if x)
    competidores = c.get("competitors") or []
    return (
        f"Empresa: {c.get('name', 'N/D')}\n"
        f"Industria: {c.get('industry', 'N/D')}\n"
        f"Región donde opera: {region or 'N/D'}\n"
        f"Sitio web: {c.get('website', 'N/D')}\n"
        f"Competidores que el usuario CREE tener: {', '.join(competidores) if competidores else 'ninguno indicado'}\n\n"
        "Investiga y entrega el diagnóstico en el JSON indicado."
    )


def parse_diagnostico(raw: str) -> dict:
    """Parsea la respuesta a {sections:[{key,title,body}], sources:[{title,url}], ...}.
    Rellena las 6 secciones (cuerpo vacío si falta). Ante basura, secciones vacías."""
    parsed = _extract_json_object(raw) or {}
    sections_in = parsed.get("sections") or {}
    sections = [
        {"key": k, "title": SECTION_TITLES[k], "body": str(sections_in.get(k) or "").strip()}
        for k in SECTION_KEYS
    ]
    sources = []
    for s in (parsed.get("sources") or []):
        if isinstance(s, dict) and s.get("url"):
            sources.append({"title": str(s.get("title") or s["url"])[:200], "url": str(s["url"])[:500]})
    return {"sections": sections, "sources": sources[:30]}


def _diagnostico_vacio(content: dict) -> bool:
    return all(not s.get("body") for s in content.get("sections", []))


def generate_diagnostico(memory_buffer: dict) -> dict:
    """Llamada de red: Opus 4.8 + web_search. Devuelve el content listo para persistir.
    Lanza RuntimeError si llega vacío/ilegible tras reintento (para marcar 'failed')."""
    if not settings.ANTHROPIC_API_KEY:
        raise RuntimeError("Falta ANTHROPIC_API_KEY para generar el diagnóstico.")

    client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    tools = [{"type": "web_search_20260209", "name": "web_search", "max_uses": _MAX_SEARCHES}]
    user_prompt = build_prompt(memory_buffer)

    for _ in range(2):  # un reintento si llega vacío
        messages = [{"role": "user", "content": user_prompt}]
        response = None
        for _ in range(_MAX_CONTINUATIONS):
            response = _create_with_retry(
                client,
                model=settings.DIAGNOSTICO_AI_MODEL,
                max_tokens=8192,
                system=SYSTEM_PROMPT,
                messages=messages,
                tools=tools,
            )
            if response.stop_reason != "pause_turn":
                break
            messages.append({"role": "assistant", "content": response.content})

        raw = "\n".join(
            b.text for b in (response.content if response else []) if getattr(b, "type", None) == "text"
        )
        content = parse_diagnostico(raw)
        if not _diagnostico_vacio(content):
            return content

    raise RuntimeError("El diagnóstico llegó vacío o ilegible tras 2 intentos.")
```

- [ ] **Step 4: Correr (pasa)**

Run: `cd backend && ./venv/bin/pytest tests/unit/test_diagnostico_engine.py -q`
Expected: PASS (4 tests). (`generate_diagnostico` no se testea con red; se mockea en Task 5.)

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/ai/diagnostico_estrategico.py backend/tests/unit/test_diagnostico_engine.py
git commit -m "feat(fase2): motor de diagnóstico con web search (Opus 4.8) + parseo"
```

---

### Task 5: Task de Celery

**Files:**
- Create: `backend/app/tasks/diagnostico_tasks.py`
- Modify: `backend/app/tasks/worker.py` (registrar el módulo)
- Test: `backend/tests/unit/test_diagnostico_task.py` (crear)

- [ ] **Step 1: Crear la task**

`backend/app/tasks/diagnostico_tasks.py`:

```python
"""Task de Celery del Diagnóstico estratégico (espejo de annual_plan_tasks)."""
import asyncio

from sqlalchemy import select

from app.tasks.worker import celery_app


@celery_app.task(name="generate_diagnostico", bind=True, max_retries=2)
def generate_diagnostico_task(self, diagnostico_id: str) -> dict:
    try:
        return asyncio.run(_entrypoint(diagnostico_id))
    except Exception as exc:
        raise self.retry(exc=exc, countdown=30)


async def _entrypoint(diagnostico_id: str) -> dict:
    from app.db.session import task_session
    async with task_session() as db:
        await _run_generation(diagnostico_id, db)
    return {"status": "active", "diagnostico_id": diagnostico_id}


async def _run_generation(diagnostico_id: str, db) -> None:
    from app.models.diagnostico_estrategico import DiagnosticoEstrategico
    from app.models.onboarding_session import OnboardingSession  # type: ignore
    from app.services.ai.diagnostico_estrategico import generate_diagnostico

    diag = (await db.execute(
        select(DiagnosticoEstrategico).where(DiagnosticoEstrategico.id == diagnostico_id)
    )).scalar_one_or_none()
    if diag is None:
        return

    try:
        onboarding = (await db.execute(
            select(OnboardingSession).where(OnboardingSession.user_id == diag.user_id)
            .order_by(OnboardingSession.created_at.desc())
        )).scalars().first()
        memory_buffer = (onboarding.memory_buffer if onboarding else {}) or {}

        content = await asyncio.to_thread(generate_diagnostico, memory_buffer)

        diag.content = content
        diag.status = "active"
        await db.commit()
    except Exception:
        await db.rollback()
        diag = (await db.execute(
            select(DiagnosticoEstrategico).where(DiagnosticoEstrategico.id == diagnostico_id)
        )).scalar_one_or_none()
        if diag is not None:
            diag.status = "failed"
            diag.fail_reason = "error"
            await db.commit()
        raise
```

> Confirmado: el modelo es `app.models.onboarding_session.OnboardingSession` con columnas `user_id`, `memory_buffer` (JSONB) y `created_at` — el mismo que usa `annual_plan_tasks.py` (`from app.models.onboarding_session import OnboardingSession`, `.where(user_id==...).order_by(created_at.desc())`).

- [ ] **Step 2: Registrar el módulo en el worker**

En `backend/app/tasks/worker.py`, agregar `"app.tasks.diagnostico_tasks"` a la lista `include=[...]`:

```python
    include=["app.tasks.document_tasks", "app.tasks.annual_plan_tasks", "app.tasks.diagnostico_tasks"],
```

- [ ] **Step 3: Test de la task (IA y DB mockeadas)**

Crear `backend/tests/unit/test_diagnostico_task.py`:

```python
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from app.tasks.diagnostico_tasks import _run_generation


@pytest.mark.asyncio
async def test_run_generation_ok():
    diag = MagicMock(); diag.user_id = "u1"; diag.status = "generating"
    onb = MagicMock(); onb.memory_buffer = {"company": {"name": "ACME"}}
    diag_res = MagicMock(); diag_res.scalar_one_or_none.return_value = diag
    onb_res = MagicMock(); onb_res.scalars.return_value.first.return_value = onb
    db = AsyncMock(); db.execute = AsyncMock(side_effect=[diag_res, onb_res]); db.commit = AsyncMock()

    fake_content = {"sections": [{"key": "resumen_ejecutivo", "title": "X", "body": "ok"}], "sources": []}
    with patch("app.tasks.diagnostico_tasks.generate_diagnostico", return_value=fake_content):
        await _run_generation("d1", db)

    assert diag.status == "active"
    assert diag.content == fake_content


@pytest.mark.asyncio
async def test_run_generation_marca_failed_en_error():
    diag = MagicMock(); diag.user_id = "u1"; diag.status = "generating"
    onb = MagicMock(); onb.memory_buffer = {}
    diag_res = MagicMock(); diag_res.scalar_one_or_none.return_value = diag
    onb_res = MagicMock(); onb_res.scalars.return_value.first.return_value = onb
    refetch = MagicMock(); refetch.scalar_one_or_none.return_value = diag
    db = AsyncMock(); db.execute = AsyncMock(side_effect=[diag_res, onb_res, refetch])
    db.commit = AsyncMock(); db.rollback = AsyncMock()

    with patch("app.tasks.diagnostico_tasks.generate_diagnostico", side_effect=RuntimeError("boom")):
        with pytest.raises(RuntimeError):
            await _run_generation("d1", db)

    assert diag.status == "failed"
    assert diag.fail_reason == "error"
```

- [ ] **Step 4: Correr (pasa)**

Run: `cd backend && ./venv/bin/pytest tests/unit/test_diagnostico_task.py -q`
Expected: PASS (2 tests). Ajustar el patch path / import del onboarding si el nombre real del modelo difiere (ver nota del Step 1).

- [ ] **Step 5: Commit**

```bash
git add backend/app/tasks/diagnostico_tasks.py backend/app/tasks/worker.py backend/tests/unit/test_diagnostico_task.py
git commit -m "feat(fase2): task de Celery del diagnóstico + registro en worker"
```

---

### Task 6: API (router + esquemas) + PDF

**Files:**
- Create: `backend/app/schemas/diagnostico.py`
- Create: `backend/app/services/pdf/diagnostico_pdf.py`
- Create: `backend/app/api/v1/diagnostico/__init__.py` (vacío) y `backend/app/api/v1/diagnostico/router.py`
- Modify: `backend/app/main.py` (registrar el router)
- Test: `backend/tests/integration/test_diagnostico_api.py` (crear)

- [ ] **Step 1: Esquemas de salida**

`backend/app/schemas/diagnostico.py`:

```python
from pydantic import BaseModel


class DiagnosticoStatusOut(BaseModel):
    status: str
    fail_reason: str | None = None


class DiagnosticoSection(BaseModel):
    key: str
    title: str
    body: str


class DiagnosticoSource(BaseModel):
    title: str
    url: str


class DiagnosticoOut(BaseModel):
    status: str
    fail_reason: str | None = None
    sections: list[DiagnosticoSection] = []
    sources: list[DiagnosticoSource] = []
```

- [ ] **Step 2: PDF**

`backend/app/services/pdf/diagnostico_pdf.py`:

```python
from io import BytesIO
from xml.sax.saxutils import escape

from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer


def build_diagnostico_pdf(content: dict, company_name: str | None) -> bytes:
    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=letter,
        topMargin=2 * cm, bottomMargin=2 * cm, leftMargin=2 * cm, rightMargin=2 * cm,
    )
    base = getSampleStyleSheet()
    h1 = ParagraphStyle("h1", parent=base["Title"], fontSize=20, spaceAfter=6)
    h2 = ParagraphStyle("h2", parent=base["Heading2"], fontSize=14, spaceBefore=14, spaceAfter=6)
    body = ParagraphStyle("body", parent=base["BodyText"], fontSize=10.5, leading=15)
    small = ParagraphStyle("small", parent=base["BodyText"], fontSize=8.5, leading=12, textColor="#666666")

    story = [
        Paragraph(escape(f"Diagnóstico estratégico — {company_name or 'tu empresa'}"), h1),
        Spacer(1, 0.3 * cm),
    ]
    for s in content.get("sections", []):
        story.append(Paragraph(escape(s.get("title", "")), h2))
        for para in (s.get("body", "") or "").split("\n"):
            if para.strip():
                story.append(Paragraph(escape(para.strip()), body))
    sources = content.get("sources", [])
    if sources:
        story.append(Paragraph("Fuentes", h2))
        for src in sources:
            story.append(Paragraph(escape(f"{src.get('title', '')} — {src.get('url', '')}"), small))
    doc.build(story)
    return buf.getvalue()
```

- [ ] **Step 3: Router**

`backend/app/api/v1/diagnostico/__init__.py`: archivo vacío.

`backend/app/api/v1/diagnostico/router.py`:

```python
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user_id, get_db
from app.models.diagnostico_estrategico import DiagnosticoEstrategico
from app.models.onboarding_session import OnboardingSession
from app.schemas.diagnostico import DiagnosticoOut, DiagnosticoStatusOut
from app.services.data_completeness import missing_diagnostico_data
from app.services.pdf.diagnostico_pdf import build_diagnostico_pdf

router = APIRouter()

_GENERATING_TIMEOUT = timedelta(minutes=20)


async def _current(user_id: str, db: AsyncSession) -> DiagnosticoEstrategico | None:
    return (await db.execute(
        select(DiagnosticoEstrategico).where(DiagnosticoEstrategico.user_id == user_id)
        .order_by(DiagnosticoEstrategico.created_at.desc())
    )).scalars().first()


async def _expire_if_stale(diag: DiagnosticoEstrategico | None, db: AsyncSession):
    if (diag is not None and diag.status == "generating" and diag.created_at is not None
            and datetime.now(timezone.utc) - diag.created_at > _GENERATING_TIMEOUT):
        diag.status = "failed"
        diag.fail_reason = "error"
        await db.commit()
    return diag


async def _memory_buffer(user_id: str, db: AsyncSession) -> dict:
    onb = (await db.execute(
        select(OnboardingSession).where(OnboardingSession.user_id == user_id)
        .order_by(OnboardingSession.created_at.desc())
    )).scalars().first()
    return (onb.memory_buffer if onb else {}) or {}


@router.post("/diagnostico/generate", response_model=DiagnosticoStatusOut)
async def generate_diagnostico_endpoint(
    user_id: str = Depends(get_current_user_id), db: AsyncSession = Depends(get_db),
):
    mb = await _memory_buffer(user_id, db)
    faltantes = missing_diagnostico_data(mb)
    if faltantes:
        raise HTTPException(
            status_code=400,
            detail="Para generar el diagnóstico necesitas completar: " + "; ".join(faltantes) + ".",
        )

    existing = await _expire_if_stale(await _current(user_id, db), db)
    if existing and existing.status == "generating":
        return DiagnosticoStatusOut(status="generating")
    # regenerar: borrar el previo (si lo hay)
    if existing is not None:
        await db.delete(existing)
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
        diag.fail_reason = "error"
        await db.commit()
        raise HTTPException(status_code=503, detail="No se pudo iniciar la generación del diagnóstico.")

    return DiagnosticoStatusOut(status="generating")


@router.get("/diagnostico/status", response_model=DiagnosticoStatusOut)
async def diagnostico_status(
    user_id: str = Depends(get_current_user_id), db: AsyncSession = Depends(get_db),
):
    diag = await _expire_if_stale(await _current(user_id, db), db)
    if not diag:
        raise HTTPException(status_code=404, detail="No hay diagnóstico generado.")
    return DiagnosticoStatusOut(status=diag.status, fail_reason=diag.fail_reason)


@router.get("/diagnostico", response_model=DiagnosticoOut)
async def get_diagnostico(
    user_id: str = Depends(get_current_user_id), db: AsyncSession = Depends(get_db),
):
    diag = await _expire_if_stale(await _current(user_id, db), db)
    if not diag:
        raise HTTPException(status_code=404, detail="No hay diagnóstico generado.")
    content = diag.content or {}
    return DiagnosticoOut(
        status=diag.status, fail_reason=diag.fail_reason,
        sections=content.get("sections", []), sources=content.get("sources", []),
    )


@router.get("/diagnostico/pdf")
async def diagnostico_pdf(
    user_id: str = Depends(get_current_user_id), db: AsyncSession = Depends(get_db),
):
    diag = await _current(user_id, db)
    if not diag or diag.status != "active" or not diag.content:
        raise HTTPException(status_code=404, detail="No hay diagnóstico disponible.")
    mb = await _memory_buffer(user_id, db)
    company_name = ((mb.get("company") or {}).get("name"))
    pdf = build_diagnostico_pdf(diag.content, company_name)
    return Response(
        content=pdf, media_type="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="diagnostico.pdf"'},
    )
```

> Confirmado: `from app.models.onboarding_session import OnboardingSession` (`user_id`, `memory_buffer`, `created_at`) — el mismo que usa `annual_plan/router.py`.

- [ ] **Step 4: Registrar el router en `main.py`**

En `backend/app/main.py`, junto a los demás imports de routers:

```python
from app.api.v1.diagnostico.router import router as diagnostico_router
```

Y en el bloque de `include_router`:

```python
app.include_router(diagnostico_router, prefix="/api/v1", tags=["diagnostico"])
```

- [ ] **Step 5: Test de integración del endpoint generate (compuerta)**

Crear `backend/tests/integration/test_diagnostico_api.py` siguiendo el patrón de `tests/integration/test_board_themes_api.py` (mismos overrides `get_db`/`get_current_user_id`):

```python
from unittest.mock import AsyncMock, MagicMock
import pytest
from httpx import ASGITransport, AsyncClient
from app.main import app
from app.core.dependencies import get_current_user_id, get_db

MOCK_USER = "user_diag_test"


def _db_override(db):
    async def override():
        yield db
    return override


async def _user_override():
    return MOCK_USER


@pytest.mark.asyncio
async def test_generate_400_si_faltan_datos(monkeypatch):
    # onboarding sin website/competitors → compuerta bloquea
    onb = MagicMock(); onb.memory_buffer = {"company": {"name": "ACME"}}
    onb_res = MagicMock(); onb_res.scalars.return_value.first.return_value = onb
    db = AsyncMock(); db.execute = AsyncMock(return_value=onb_res)

    app.dependency_overrides[get_db] = _db_override(db)
    app.dependency_overrides[get_current_user_id] = _user_override
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.post("/api/v1/diagnostico/generate")
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 400
    assert "completar" in r.json()["detail"].lower()


@pytest.mark.asyncio
async def test_status_404_si_no_hay(monkeypatch):
    none_res = MagicMock(); none_res.scalars.return_value.first.return_value = None
    db = AsyncMock(); db.execute = AsyncMock(return_value=none_res); db.commit = AsyncMock()

    app.dependency_overrides[get_db] = _db_override(db)
    app.dependency_overrides[get_current_user_id] = _user_override
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.get("/api/v1/diagnostico/status")
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 404
```

- [ ] **Step 6: Correr toda la suite nueva + la existente**

Run: `cd backend && ./venv/bin/pytest tests/unit/test_etapa1_seed_fields.py tests/unit/test_diagnostico_completeness.py tests/unit/test_diagnostico_engine.py tests/unit/test_diagnostico_task.py tests/integration/test_diagnostico_api.py -q`
Expected: PASS. Luego `./venv/bin/pytest -q` completo para confirmar que no se rompió nada existente.

- [ ] **Step 7: Commit**

```bash
git add backend/app/schemas/diagnostico.py backend/app/services/pdf/diagnostico_pdf.py backend/app/api/v1/diagnostico/ backend/app/main.py backend/tests/integration/test_diagnostico_api.py
git commit -m "feat(fase2): API del diagnóstico (generate/status/get/pdf) + PDF reportlab"
```

---

## Self-Review (cobertura del spec)

- **Componente 1 (campos onboarding)** → Task 1 (opcionales en schema + memory_buffer; obligatoriedad vía compuerta — refinación de deploy-safety documentada). El **form del frontend** va en el plan de frontend. ✅
- **Componente 2 (modelo + migración)** → Task 3. ✅
- **Componente 3 (motor IA web search)** → Task 4 (`build_prompt`/`parse_diagnostico`/`generate_diagnostico`, Opus 4.8, `web_search_20260209`, `max_uses`, pause_turn loop, sin structured-outputs). ✅
- **Componente 4 (task Celery)** → Task 5 (`task_session`, status, registro en worker). ✅
- **Componente 5 (API)** → Task 6 (generate/status/get/pdf). ✅
- **Componente 6 (compuerta)** → Task 2 (`missing_diagnostico_data`). ✅
- **Componente 8 (PDF)** → Task 6. ✅
- **Componente 7 (frontend)** → NO está aquí (plan de frontend aparte). ✅ (separación intencional)

Consistencia de tipos: las 6 keys de `SECTION_KEYS` se usan igual en motor, parser y tests; `content` = `{sections:[{key,title,body}], sources:[{title,url}]}` consistente entre motor, task, modelo (JSONB), router y PDF. `missing_diagnostico_data` devuelve `list[str]` (vacía = ok), consumida por el router con 400.

Puntos a confirmar en implementación (marcados en el plan): el nombre real del modelo/columnas del onboarding (`OnboardingSession`) — reusar el que ya usan `annual_plan_tasks.py` / `annual_plan/router.py`. La aplicación real de la migración (`alembic upgrade head`) se hace en integración/deploy, no en una task.
