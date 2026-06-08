# Bloque B1 — Temas del Consejo · Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Agregar la entidad `BoardTheme` (Tema del Consejo) con catálogo por defecto editable, sembrado por plan, CRUD y gestión desde el dashboard — la fundación del motor de cobertura.

**Architecture:** Nueva tabla `board_themes` colgando de `annual_plans` (FK + DB cascade). Un catálogo determinista de 13 temas se siembra al crear un `AnnualPlan`. Endpoints REST nuevos en el router existente de annual-plan, sobre el plan activo del usuario. Frontend: sección "Temas del Consejo" en `/dashboard/plan`.

**Tech Stack:** FastAPI, SQLAlchemy async (Mapped/mapped_column), Pydantic v2, pytest (asyncio, db mockeada con AsyncMock), Next.js 16 + TypeScript, axios.

**Spec:** `docs/superpowers/specs/2026-06-08-bloque-b1-temas-consejo-design.md`

---

### Task 1: Modelo `BoardTheme` + registro + script de tabla

**Files:**
- Create: `backend/app/models/board_theme.py`
- Modify: `backend/app/models/__init__.py`
- Create: `backend/scripts/create_board_themes.py`
- Test: `backend/tests/unit/test_board_theme_model.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/unit/test_board_theme_model.py
from app.models import Base
from app.models.board_theme import BoardTheme


def test_board_themes_table_registered():
    table = Base.metadata.tables.get("board_themes")
    assert table is not None
    cols = set(table.columns.keys())
    assert {"id", "annual_plan_id", "key", "label", "type",
            "every_n_sessions", "active", "is_default", "order_index",
            "created_at", "updated_at"} <= cols


def test_board_theme_instantiable():
    t = BoardTheme(annual_plan_id=None, key="finanzas", label="Finanzas",
                   type="permanente", every_n_sessions=1)
    assert t.key == "finanzas"
    assert t.type == "permanente"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && venv/bin/python -m pytest tests/unit/test_board_theme_model.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.models.board_theme'`

- [ ] **Step 3: Create the model**

```python
# backend/app/models/board_theme.py
import uuid

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin


class BoardTheme(Base, UUIDMixin, TimestampMixin):
    """Tema del Consejo: responsabilidad que el Consejo debe cubrir en el año.
    type: permanente (cada sesión) | cobertura (rota por frecuencia) | emergente."""
    __tablename__ = "board_themes"
    __table_args__ = (
        UniqueConstraint("annual_plan_id", "key", name="uq_board_theme_plan_key"),
    )

    annual_plan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("annual_plans.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    key:   Mapped[str] = mapped_column(String(60), nullable=False)
    label: Mapped[str] = mapped_column(Text, nullable=False)
    type:  Mapped[str] = mapped_column(String(20), nullable=False)
    # 1=cada sesión, 2=bimestral, 3=trimestral, 6=semestral, 12=anual; null para emergente
    every_n_sessions: Mapped[int | None] = mapped_column(Integer, nullable=True)
    active:      Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_default:  Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    order_index: Mapped[int]  = mapped_column(Integer, nullable=False, default=0)
```

- [ ] **Step 4: Register the model**

In `backend/app/models/__init__.py`, add the import after the annual_plan import and extend `__all__`:

```python
from app.models.annual_plan import AnnualPlan, MonthlyPlan, Objective
from app.models.board_theme import BoardTheme

__all__ = [
    "Base", "OnboardingSession", "Document", "BoardSession", "ChatMessage",
    "ActionPlan", "ActionTask", "AnnualPlan", "MonthlyPlan", "Objective",
    "BoardTheme",
]
```

- [ ] **Step 5: Create the table-creation script**

```python
# backend/scripts/create_board_themes.py
"""Crea la tabla board_themes SIN Alembic (prod aplica esquema con create_all).
Idempotente: create_all omite tablas existentes.

USO (solo cuando el humano lo autorice — toca la DB):
    venv/bin/python -m scripts.create_board_themes
"""
import asyncio

from app.db.session import engine
import app.models  # noqa: F401  (registra todos los modelos en Base.metadata)
from app.models import Base


async def main():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await engine.dispose()
    print("OK: tabla board_themes creada")


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 6: Run test to verify it passes**

Run: `cd backend && venv/bin/python -m pytest tests/unit/test_board_theme_model.py -v`
Expected: PASS (2 passed)

- [ ] **Step 7: Commit**

```bash
git add backend/app/models/board_theme.py backend/app/models/__init__.py backend/scripts/create_board_themes.py backend/tests/unit/test_board_theme_model.py
git commit -m "feat(b1): modelo BoardTheme + registro + script de tabla"
```

---

### Task 2: Catálogo de temas por defecto

**Files:**
- Create: `backend/app/services/governance/__init__.py`
- Create: `backend/app/services/governance/default_themes.py`
- Test: `backend/tests/unit/test_default_themes.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/unit/test_default_themes.py
from app.services.governance.default_themes import DEFAULT_THEMES


def test_catalog_has_13_themes():
    assert len(DEFAULT_THEMES) == 13


def test_catalog_type_counts():
    perm = [t for t in DEFAULT_THEMES if t["type"] == "permanente"]
    cob = [t for t in DEFAULT_THEMES if t["type"] == "cobertura"]
    assert len(perm) == 5
    assert len(cob) == 8
    assert all(t["every_n_sessions"] == 1 for t in perm)


def test_catalog_keys_unique():
    keys = [t["key"] for t in DEFAULT_THEMES]
    assert len(keys) == len(set(keys))


def test_cobertura_frequencies():
    by_key = {t["key"]: t["every_n_sessions"] for t in DEFAULT_THEMES}
    assert by_key["talento_sucesion"] == 2
    assert by_key["auditoria"] == 3
    assert by_key["planeacion_estrategica"] == 6
    assert by_key["evaluacion_consejo"] == 12
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && venv/bin/python -m pytest tests/unit/test_default_themes.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Create the catalog**

```python
# backend/app/services/governance/__init__.py
```

```python
# backend/app/services/governance/default_themes.py
"""Catálogo por defecto de Temas del Consejo (Bloque B1).
Se siembra al crear un AnnualPlan. every_n_sessions: 1=cada sesión, 2=bimestral,
3=trimestral, 6=semestral, 12=anual."""

DEFAULT_THEMES: list[dict] = [
    # Permanentes — aparecen en TODAS las sesiones
    {"key": "seguimiento_acuerdos",   "label": "Seguimiento de acuerdos", "type": "permanente", "every_n_sessions": 1},
    {"key": "resultados_financieros", "label": "Resultados financieros",  "type": "permanente", "every_n_sessions": 1},
    {"key": "resultados_operativos",  "label": "Resultados operativos",   "type": "permanente", "every_n_sessions": 1},
    {"key": "kpis_estrategicos",      "label": "KPIs estratégicos",       "type": "permanente", "every_n_sessions": 1},
    {"key": "riesgos_criticos",       "label": "Riesgos críticos",        "type": "permanente", "every_n_sessions": 1},
    # Cobertura — rotan por frecuencia
    {"key": "talento_sucesion",           "label": "Talento y sucesión",            "type": "cobertura", "every_n_sessions": 2},
    {"key": "tecnologia_ciberseguridad",  "label": "Tecnología y ciberseguridad",   "type": "cobertura", "every_n_sessions": 2},
    {"key": "auditoria",                  "label": "Auditoría",                     "type": "cobertura", "every_n_sessions": 3},
    {"key": "cumplimiento_normativo",     "label": "Cumplimiento normativo",        "type": "cobertura", "every_n_sessions": 3},
    {"key": "esg",                        "label": "ESG / Sostenibilidad",          "type": "cobertura", "every_n_sessions": 3},
    {"key": "planeacion_estrategica",     "label": "Planeación estratégica",        "type": "cobertura", "every_n_sessions": 6},
    {"key": "evaluacion_dg",              "label": "Evaluación del Director General", "type": "cobertura", "every_n_sessions": 12},
    {"key": "evaluacion_consejo",         "label": "Evaluación del Consejo",        "type": "cobertura", "every_n_sessions": 12},
]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && venv/bin/python -m pytest tests/unit/test_default_themes.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/governance/__init__.py backend/app/services/governance/default_themes.py backend/tests/unit/test_default_themes.py
git commit -m "feat(b1): catálogo por defecto de Temas del Consejo (13)"
```

---

### Task 3: Función `seed_default_themes` (idempotente)

**Files:**
- Create: `backend/app/services/governance/theme_seeder.py`
- Test: `backend/tests/unit/test_theme_seeder.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/unit/test_theme_seeder.py
import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.governance.theme_seeder import seed_default_themes


def _db_no_existing():
    """db.execute(...).first() -> None  => no hay temas aún."""
    result = MagicMock()
    result.first.return_value = None
    db = AsyncMock()
    db.execute = AsyncMock(return_value=result)
    db.add = MagicMock()
    db.flush = AsyncMock()
    return db


def _db_with_existing():
    result = MagicMock()
    result.first.return_value = ("some-id",)
    db = AsyncMock()
    db.execute = AsyncMock(return_value=result)
    db.add = MagicMock()
    db.flush = AsyncMock()
    return db


@pytest.mark.asyncio
async def test_seeds_13_when_empty():
    db = _db_no_existing()
    n = await seed_default_themes(db, uuid.uuid4())
    assert n == 13
    assert db.add.call_count == 13


@pytest.mark.asyncio
async def test_idempotent_when_existing():
    db = _db_with_existing()
    n = await seed_default_themes(db, uuid.uuid4())
    assert n == 0
    db.add.assert_not_called()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && venv/bin/python -m pytest tests/unit/test_theme_seeder.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement the seeder**

```python
# backend/app/services/governance/theme_seeder.py
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.board_theme import BoardTheme
from app.services.governance.default_themes import DEFAULT_THEMES


async def seed_default_themes(db: AsyncSession, annual_plan_id: uuid.UUID) -> int:
    """Siembra el catálogo por defecto si el plan aún no tiene temas.
    Idempotente. Devuelve cuántos temas insertó."""
    existing = await db.execute(
        select(BoardTheme.id).where(BoardTheme.annual_plan_id == annual_plan_id).limit(1)
    )
    if existing.first() is not None:
        return 0
    for i, t in enumerate(DEFAULT_THEMES):
        db.add(BoardTheme(
            annual_plan_id=annual_plan_id,
            key=t["key"], label=t["label"], type=t["type"],
            every_n_sessions=t["every_n_sessions"],
            is_default=True, active=True, order_index=i,
        ))
    await db.flush()
    return len(DEFAULT_THEMES)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && venv/bin/python -m pytest tests/unit/test_theme_seeder.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/governance/theme_seeder.py backend/tests/unit/test_theme_seeder.py
git commit -m "feat(b1): seed_default_themes idempotente"
```

---

### Task 4: Esquemas Pydantic + validación

**Files:**
- Create: `backend/app/schemas/board_theme.py`
- Test: `backend/tests/unit/test_board_theme_schemas.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/unit/test_board_theme_schemas.py
import pytest
from pydantic import ValidationError

from app.schemas.board_theme import BoardThemeCreate, BoardThemeUpdate


def test_permanente_forces_freq_1():
    m = BoardThemeCreate(label="X", type="permanente", every_n_sessions=6)
    assert m.every_n_sessions == 1


def test_emergente_forces_null():
    m = BoardThemeCreate(label="X", type="emergente", every_n_sessions=3)
    assert m.every_n_sessions is None


def test_cobertura_rejects_bad_freq():
    with pytest.raises(ValidationError):
        BoardThemeCreate(label="X", type="cobertura", every_n_sessions=5)


def test_cobertura_accepts_valid_freq():
    m = BoardThemeCreate(label="X", type="cobertura", every_n_sessions=3)
    assert m.every_n_sessions == 3


def test_update_rejects_bad_freq():
    with pytest.raises(ValidationError):
        BoardThemeUpdate(every_n_sessions=7)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && venv/bin/python -m pytest tests/unit/test_board_theme_schemas.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement the schemas**

```python
# backend/app/schemas/board_theme.py
from typing import Literal

from pydantic import BaseModel, field_validator, model_validator

ThemeType = Literal["permanente", "cobertura", "emergente"]
VALID_FREQ = {1, 2, 3, 6, 12}


class BoardThemeOut(BaseModel):
    id: str
    key: str
    label: str
    type: str
    every_n_sessions: int | None = None
    active: bool
    is_default: bool
    order_index: int


class BoardThemeCreate(BaseModel):
    label: str
    type: ThemeType
    every_n_sessions: int | None = None

    @model_validator(mode="after")
    def _normalize_freq(self):
        if self.type == "permanente":
            self.every_n_sessions = 1
        elif self.type == "emergente":
            self.every_n_sessions = None
        elif self.every_n_sessions not in VALID_FREQ:
            raise ValueError("every_n_sessions debe ser 1, 2, 3, 6 o 12")
        return self


class BoardThemeUpdate(BaseModel):
    label: str | None = None
    every_n_sessions: int | None = None
    active: bool | None = None
    order_index: int | None = None

    @field_validator("every_n_sessions")
    @classmethod
    def _check_freq(cls, v):
        if v is not None and v not in VALID_FREQ:
            raise ValueError("every_n_sessions debe ser 1, 2, 3, 6 o 12")
        return v
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && venv/bin/python -m pytest tests/unit/test_board_theme_schemas.py -v`
Expected: PASS (5 passed)

- [ ] **Step 5: Commit**

```bash
git add backend/app/schemas/board_theme.py backend/tests/unit/test_board_theme_schemas.py
git commit -m "feat(b1): esquemas Pydantic de BoardTheme con validación de frecuencia"
```

---

### Task 5: Endpoints CRUD de temas

**Files:**
- Modify: `backend/app/api/v1/annual_plan/router.py` (añadir imports + helper + 4 endpoints al final)
- Test: `backend/tests/integration/test_board_themes_api.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/integration/test_board_themes_api.py
import uuid
from datetime import date
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.core.dependencies import get_current_user_id, get_db

MOCK_USER_ID = "user_test_themes"


def _plan():
    p = MagicMock()
    p.id = uuid.uuid4()
    p.user_id = MOCK_USER_ID
    p.status = "active"
    p.start_date = date.today()
    return p


def _theme(label="Finanzas", type_="permanente", freq=1):
    t = MagicMock()
    t.id = uuid.uuid4()
    t.key = "finanzas"
    t.label = label
    t.type = type_
    t.every_n_sessions = freq
    t.active = True
    t.is_default = True
    t.order_index = 0
    return t


def _db_for_list(plan, themes):
    """_current_plan usa scalar_one_or_none; list usa scalars().all()."""
    result = MagicMock()
    result.scalar_one_or_none.return_value = plan
    result.scalars.return_value.all.return_value = themes
    db = AsyncMock()
    db.execute = AsyncMock(return_value=result)
    db.flush = AsyncMock()
    db.commit = AsyncMock()
    return db


def _db_override(db):
    async def override():
        yield db
    return override


async def _user_override():
    return MOCK_USER_ID


@pytest.mark.asyncio
async def test_list_themes_returns_themes():
    db = _db_for_list(_plan(), [_theme(), _theme("Riesgos")])
    app.dependency_overrides[get_db] = _db_override(db)
    app.dependency_overrides[get_current_user_id] = _user_override
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.get("/api/v1/annual-plan/themes")
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 200
    assert len(r.json()) == 2
    assert r.json()[0]["label"] == "Finanzas"


@pytest.mark.asyncio
async def test_list_themes_404_when_no_plan():
    db = _db_for_list(None, [])
    app.dependency_overrides[get_db] = _db_override(db)
    app.dependency_overrides[get_current_user_id] = _user_override
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.get("/api/v1/annual-plan/themes")
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_patch_theme_404_when_not_owned():
    result = MagicMock()
    result.scalar_one_or_none.return_value = None  # _load_owned_theme no encuentra
    db = AsyncMock()
    db.execute = AsyncMock(return_value=result)
    db.flush = AsyncMock()
    app.dependency_overrides[get_db] = _db_override(db)
    app.dependency_overrides[get_current_user_id] = _user_override
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.patch(f"/api/v1/annual-plan/themes/{uuid.uuid4()}", json={"active": False})
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_create_theme_validation_422():
    db = _db_for_list(_plan(), [])
    app.dependency_overrides[get_db] = _db_override(db)
    app.dependency_overrides[get_current_user_id] = _user_override
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.post("/api/v1/annual-plan/themes",
                             json={"label": "X", "type": "cobertura", "every_n_sessions": 5})
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 422
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && venv/bin/python -m pytest tests/integration/test_board_themes_api.py -v`
Expected: FAIL (404/405 — los endpoints no existen aún)

- [ ] **Step 3: Add imports to the router**

In `backend/app/api/v1/annual_plan/router.py`, add after the existing schema imports (near line 30):

```python
from app.models.board_theme import BoardTheme
from app.schemas.board_theme import BoardThemeOut, BoardThemeCreate, BoardThemeUpdate
```

- [ ] **Step 4: Add helper + endpoints at the end of the router file**

```python
# ── Temas del Consejo (B1) ────────────────────────────────────────────────────

def _theme_out(t: BoardTheme) -> BoardThemeOut:
    return BoardThemeOut(
        id=str(t.id), key=t.key, label=t.label, type=t.type,
        every_n_sessions=t.every_n_sessions, active=t.active,
        is_default=t.is_default, order_index=t.order_index,
    )


def _slugify(label: str) -> str:
    base = "".join(c if c.isalnum() else "_" for c in label.lower()).strip("_")
    return (base or "tema")[:50] + "_" + uuid.uuid4().hex[:6]


async def _load_owned_theme(theme_id: uuid.UUID, user_id: str, db: AsyncSession) -> BoardTheme:
    res = await db.execute(
        select(BoardTheme)
        .join(AnnualPlan, BoardTheme.annual_plan_id == AnnualPlan.id)
        .where(BoardTheme.id == theme_id, AnnualPlan.user_id == user_id)
    )
    theme = res.scalar_one_or_none()
    if not theme:
        raise HTTPException(status_code=404, detail="Tema no encontrado")
    return theme


@router.get("/annual-plan/themes", response_model=list[BoardThemeOut])
async def list_themes(
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    plan = await _current_plan(user_id, db)
    if not plan:
        raise HTTPException(status_code=404, detail="No tienes un plan anual")
    res = await db.execute(
        select(BoardTheme)
        .where(BoardTheme.annual_plan_id == plan.id)
        .order_by(BoardTheme.type, BoardTheme.order_index)
    )
    return [_theme_out(t) for t in res.scalars().all()]


@router.post("/annual-plan/themes", response_model=BoardThemeOut)
async def create_theme(
    body: BoardThemeCreate,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    plan = await _current_plan(user_id, db)
    if not plan:
        raise HTTPException(status_code=404, detail="No tienes un plan anual")
    theme = BoardTheme(
        annual_plan_id=plan.id, key=_slugify(body.label), label=body.label,
        type=body.type, every_n_sessions=body.every_n_sessions,
        is_default=False, active=True, order_index=999,
    )
    db.add(theme)
    await db.flush()
    return _theme_out(theme)


@router.patch("/annual-plan/themes/{theme_id}", response_model=BoardThemeOut)
async def update_theme(
    theme_id: uuid.UUID,
    body: BoardThemeUpdate,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    theme = await _load_owned_theme(theme_id, user_id, db)
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(theme, field, value)
    await db.flush()
    return _theme_out(theme)


@router.delete("/annual-plan/themes/{theme_id}", status_code=204)
async def delete_theme(
    theme_id: uuid.UUID,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    theme = await _load_owned_theme(theme_id, user_id, db)
    await db.delete(theme)
    await db.flush()
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd backend && venv/bin/python -m pytest tests/integration/test_board_themes_api.py -v`
Expected: PASS (4 passed)

- [ ] **Step 6: Commit**

```bash
git add backend/app/api/v1/annual_plan/router.py backend/tests/integration/test_board_themes_api.py
git commit -m "feat(b1): endpoints CRUD de Temas del Consejo"
```

---

### Task 6: Sembrar temas al crear el plan

**Files:**
- Modify: `backend/app/api/v1/annual_plan/router.py` (`generate_plan`, ~líneas 102-108)
- Modify: `backend/app/api/v1/onboarding/etapa8.py` (creación del AnnualPlan, ~líneas 124-130)
- Test: `backend/tests/integration/test_board_themes_api.py` (añadir caso)

- [ ] **Step 1: Write the failing test**

Añade a `backend/tests/integration/test_board_themes_api.py`:

```python
@pytest.mark.asyncio
async def test_generate_seeds_themes(monkeypatch):
    """generate_plan crea el plan y siembra los temas por defecto."""
    seeded = {"called": False, "count": 0}

    async def fake_seed(db, plan_id):
        seeded["called"] = True
        seeded["count"] = 13
        return 13

    monkeypatch.setattr("app.api.v1.annual_plan.router.seed_default_themes", fake_seed)

    # _current_plan -> None (no hay plan previo) y .delay no disponible -> 503 controlado,
    # pero el seed debe llamarse ANTES de encolar.
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    db = AsyncMock()
    db.execute = AsyncMock(return_value=result)
    db.add = MagicMock()
    db.flush = AsyncMock()
    db.commit = AsyncMock()

    def boom(*a, **k):
        raise RuntimeError("no celery")
    monkeypatch.setattr("app.tasks.annual_plan_tasks.generate_annual_plan_task.delay", boom)

    app.dependency_overrides[get_db] = _db_override(db)
    app.dependency_overrides[get_current_user_id] = _user_override
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            await c.post("/api/v1/annual-plan/generate")
    finally:
        app.dependency_overrides.clear()
    assert seeded["called"] is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && venv/bin/python -m pytest tests/integration/test_board_themes_api.py::test_generate_seeds_themes -v`
Expected: FAIL (`seed_default_themes` no está importado en el router / no se llama)

- [ ] **Step 3: Wire seed into `generate_plan`**

In `backend/app/api/v1/annual_plan/router.py`, add the import (near the other service imports, ~line 31):

```python
from app.services.governance.theme_seeder import seed_default_themes
```

Then in `generate_plan`, after `db.add(plan)` / `await db.flush()` and BEFORE the final commit, seed the themes. Replace:

```python
    plan = AnnualPlan(
        user_id=user_id, title="Plan estratégico de 12 meses",
        start_date=date.today(), status="generating",
    )
    db.add(plan)
    await db.flush()
    await db.commit()
```

with:

```python
    plan = AnnualPlan(
        user_id=user_id, title="Plan estratégico de 12 meses",
        start_date=date.today(), status="generating",
    )
    db.add(plan)
    await db.flush()
    await seed_default_themes(db, plan.id)
    await db.commit()
```

- [ ] **Step 4: Wire seed into the etapa-8 hook**

In `backend/app/api/v1/onboarding/etapa8.py`, inside the best-effort block that creates the `AnnualPlan` (after `db.add(plan)` / `await db.flush()` / `await db.commit()`, ~line 128-130), add a best-effort seed. Add the import locally in that block:

```python
                db.add(plan)
                await db.flush()
                await db.commit()
                try:
                    from app.services.governance.theme_seeder import seed_default_themes
                    await seed_default_themes(db, plan.id)
                    await db.commit()
                except Exception:
                    logging.getLogger(__name__).warning("No se pudieron sembrar temas del plan", exc_info=True)
```

(Keep the existing `.delay()` enqueue that follows.)

- [ ] **Step 5: Run test to verify it passes**

Run: `cd backend && venv/bin/python -m pytest tests/integration/test_board_themes_api.py -v`
Expected: PASS (5 passed)

- [ ] **Step 6: Run the full backend suite (no regressions)**

Run: `cd backend && venv/bin/python -m pytest -q`
Expected: all pass (prior 273 + nuevos)

- [ ] **Step 7: Commit**

```bash
git add backend/app/api/v1/annual_plan/router.py backend/app/api/v1/onboarding/etapa8.py backend/tests/integration/test_board_themes_api.py
git commit -m "feat(b1): sembrar temas por defecto al crear el plan (generate + etapa8)"
```

---

### Task 7: Script de backfill para planes existentes

**Files:**
- Create: `backend/scripts/seed_board_themes.py`

- [ ] **Step 1: Create the backfill script**

```python
# backend/scripts/seed_board_themes.py
"""Backfill: siembra los Temas del Consejo por defecto en planes existentes.
Idempotente (no duplica si el plan ya tiene temas).

USO (solo cuando el humano lo autorice — toca la DB):
    venv/bin/python -m scripts.seed_board_themes --all
    venv/bin/python -m scripts.seed_board_themes <annual_plan_id>
"""
import asyncio
import sys

from sqlalchemy import select

from app.db.session import AsyncSessionLocal
from app.models.annual_plan import AnnualPlan
from app.services.governance.theme_seeder import seed_default_themes


async def main(arg: str):
    async with AsyncSessionLocal() as db:
        if arg == "--all":
            res = await db.execute(select(AnnualPlan.id))
            ids = [row[0] for row in res.all()]
        else:
            ids = [arg]
        total = 0
        for pid in ids:
            n = await seed_default_themes(db, pid)
            total += n
            print(f"plan {pid}: +{n} temas")
        await db.commit()
        print(f"OK: {total} temas sembrados en {len(ids)} plan(es)")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("USO: python -m scripts.seed_board_themes <annual_plan_id|--all>")
        sys.exit(1)
    asyncio.run(main(sys.argv[1]))
```

- [ ] **Step 2: Verify it imports cleanly (no DB run yet)**

Run: `cd backend && venv/bin/python -c "import scripts.seed_board_themes; print('import OK')"`
Expected: `import OK`

- [ ] **Step 3: Commit**

```bash
git add backend/scripts/seed_board_themes.py
git commit -m "feat(b1): script de backfill de temas para planes existentes"
```

> **Nota de despliegue (manual, requiere autorización humana):** tras desplegar, correr en el backend de Railway `python -m scripts.create_board_themes` (crea la tabla) y luego `python -m scripts.seed_board_themes --all` (siembra planes existentes, incluido el de `c.beuvrin@ketingmedia.com`).

---

### Task 8: Frontend — lib + panel de Temas en `/dashboard/plan`

**Files:**
- Create: `frontend/src/lib/boardThemes.ts`
- Create: `frontend/src/components/plan/ThemesPanel.tsx`
- Modify: `frontend/src/app/dashboard/plan/page.tsx` (montar el panel en la vista `active`)

- [ ] **Step 1: Create the API lib**

```typescript
// frontend/src/lib/boardThemes.ts
import api from "@/lib/api"

export type ThemeType = "permanente" | "cobertura" | "emergente"

export interface BoardTheme {
  id: string
  key: string
  label: string
  type: ThemeType
  every_n_sessions: number | null
  active: boolean
  is_default: boolean
  order_index: number
}

export const FREQ_LABEL: Record<number, string> = {
  1: "cada sesión",
  2: "bimestral",
  3: "trimestral",
  6: "semestral",
  12: "anual",
}

export async function getThemes(): Promise<BoardTheme[]> {
  const r = await api.get<BoardTheme[]>("/annual-plan/themes")
  return r.data
}

export async function createTheme(body: {
  label: string
  type: ThemeType
  every_n_sessions: number | null
}): Promise<BoardTheme> {
  const r = await api.post<BoardTheme>("/annual-plan/themes", body)
  return r.data
}

export async function updateTheme(
  id: string,
  patch: Partial<Pick<BoardTheme, "label" | "every_n_sessions" | "active" | "order_index">>,
): Promise<BoardTheme> {
  const r = await api.patch<BoardTheme>(`/annual-plan/themes/${id}`, patch)
  return r.data
}

export async function deleteTheme(id: string): Promise<void> {
  await api.delete(`/annual-plan/themes/${id}`)
}
```

- [ ] **Step 2: Create the ThemesPanel component**

```tsx
// frontend/src/components/plan/ThemesPanel.tsx
"use client"

import { useEffect, useState } from "react"
import {
  BoardTheme, FREQ_LABEL, getThemes, updateTheme, createTheme, deleteTheme,
} from "@/lib/boardThemes"
import InfoHint from "@/components/ui/InfoHint"

const FREQ_OPTIONS = [1, 2, 3, 6, 12]
const TYPE_TITLES: Record<string, string> = {
  permanente: "Permanentes — cada sesión",
  cobertura: "Cobertura — rotan por frecuencia",
  emergente: "Emergentes — los inyecta el Secretario",
}

export default function ThemesPanel() {
  const [themes, setThemes] = useState<BoardTheme[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    getThemes().then(setThemes).catch(() => {}).finally(() => setLoading(false))
  }, [])

  const patch = async (id: string, p: Partial<BoardTheme>) => {
    setThemes(ts => ts.map(t => (t.id === id ? { ...t, ...p } : t)))
    await updateTheme(id, p).catch(() => getThemes().then(setThemes))
  }

  const remove = async (id: string) => {
    setThemes(ts => ts.filter(t => t.id !== id))
    await deleteTheme(id).catch(() => getThemes().then(setThemes))
  }

  const addCustom = async () => {
    const label = window.prompt("Nombre del tema")
    if (!label) return
    const created = await createTheme({ label, type: "cobertura", every_n_sessions: 3 })
    setThemes(ts => [...ts, created])
  }

  if (loading) return <p className="text-sm text-gray-400">Cargando temas…</p>

  const byType = (t: string) => themes.filter(x => x.type === t)

  return (
    <div className="space-y-8">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-bold text-black flex items-center gap-2">
          Temas del Consejo
          <InfoHint text="Las responsabilidades que el Consejo debe cubrir en el año. La frecuencia indica cada cuántas sesiones se revisa cada tema." />
        </h2>
        <button onClick={addCustom} className="text-xs font-medium text-[var(--gob-navy)] hover:underline">
          + Agregar tema
        </button>
      </div>

      {["permanente", "cobertura", "emergente"].map(type => {
        const list = byType(type)
        if (type === "emergente" && list.length === 0) return null
        return (
          <div key={type} className="space-y-3">
            <p className="text-xs font-medium uppercase tracking-wide text-gray-400">{TYPE_TITLES[type]}</p>
            <div className="space-y-2">
              {list.map(t => (
                <div key={t.id} className={`flex items-center gap-3 rounded-xl border border-gray-100 px-4 py-3 ${t.active ? "" : "opacity-50"}`}>
                  <span className="flex-1 text-sm text-black">{t.label}</span>
                  {t.type === "cobertura" && (
                    <select
                      value={t.every_n_sessions ?? 3}
                      onChange={e => patch(t.id, { every_n_sessions: Number(e.target.value) })}
                      className="text-xs border border-gray-200 rounded-lg px-2 py-1 text-gray-700"
                    >
                      {FREQ_OPTIONS.map(f => <option key={f} value={f}>{FREQ_LABEL[f]}</option>)}
                    </select>
                  )}
                  {t.type === "permanente" && (
                    <span className="text-xs text-gray-400">cada sesión</span>
                  )}
                  <button
                    onClick={() => patch(t.id, { active: !t.active })}
                    className="text-xs text-gray-500 hover:text-[var(--gob-navy)]"
                  >
                    {t.active ? "Desactivar" : "Activar"}
                  </button>
                  {!t.is_default && (
                    <button onClick={() => remove(t.id)} className="text-xs text-red-400 hover:text-red-600">
                      Borrar
                    </button>
                  )}
                </div>
              ))}
            </div>
          </div>
        )
      })}
    </div>
  )
}
```

- [ ] **Step 3: Mount the panel in the plan page**

In `frontend/src/app/dashboard/plan/page.tsx`, import the panel near the other plan-component imports:

```typescript
import ThemesPanel from "@/components/plan/ThemesPanel"
```

Then in the `active` view's JSX (where the plan/months render), add the panel below the existing content, inside the same container:

```tsx
        <div className="mt-12 border-t border-gray-100 pt-10">
          <ThemesPanel />
        </div>
```

(If the engineer cannot identify the exact container, mount `<ThemesPanel />` at the end of the `active` view's returned tree, inside the outermost padded `<div>`.)

- [ ] **Step 4: Typecheck and build**

Run: `cd frontend && npx tsc --noEmit && npx eslint src/lib/boardThemes.ts src/components/plan/ThemesPanel.tsx && npm run build`
Expected: TSC OK, lint clean, `✓ Compiled successfully`

- [ ] **Step 5: Commit**

```bash
git add frontend/src/lib/boardThemes.ts frontend/src/components/plan/ThemesPanel.tsx frontend/src/app/dashboard/plan/page.tsx
git commit -m "feat(b1): panel de Temas del Consejo en /dashboard/plan"
```

---

## Done criteria

- `board_themes` existe (script `create_board_themes` corrido en prod) y todo plan nuevo nace con 13 temas; backfill corrido para planes existentes.
- El dueño ve y edita el catálogo de temas desde `/dashboard/plan`.
- Suite backend verde; `tsc` + `npm run build` verdes.

## Notes for the implementer

- **DB mockeada en tests:** los tests de integración NO tocan una DB real; mockean `get_db` con `AsyncMock` (ver `tests/integration/test_annual_plan_api.py`). `db.execute` devuelve un `MagicMock` configurado por test.
- **Migraciones en prod:** Gobernia aplica esquema con `create_all` vía scripts (no Alembic en runtime). El script `create_board_themes.py` es lo que realmente se corre; no hace falta un archivo Alembic.
- **Best-effort en onboarding:** el seed en etapa-8 va envuelto en try/except para no romper el onboarding si algo falla (igual que el hardening existente del hook).
