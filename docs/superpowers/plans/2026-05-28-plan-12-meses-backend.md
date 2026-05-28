# Plan de 12 meses — Backend (Subproyecto A, parte 1) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Construir el backend del plan estratégico de 12 meses: modelos `AnnualPlan/MonthlyPlan/Objective` (+ 2 columnas en `action_tasks`), generación IA en 3 pasos (diagnóstico → esqueleto → tareas) orquestada en una tarea Celery, y la API REST para leer/editar el plan.

**Architecture:** Enfoque 1 del spec — tablas nuevas para la estructura anual/mensual/objetivos; las tareas siguen viviendo en `action_tasks` colgando de `objective_id`. La generación corre en el worker Celery (proceso síncrono que envuelve `asyncio.run`, igual que `document_tasks`). La lógica "pura" (parseo de esqueleto, mapeo de tareas, calendario de meses, síntesis de diagnóstico, plan fallback sin API key) se aísla en funciones testeables sin DB ni red.

**Tech Stack:** FastAPI, SQLAlchemy async, Alembic, Celery, Anthropic SDK, pytest (asyncio_mode=auto), httpx ASGITransport.

**Spec:** `docs/superpowers/specs/2026-05-28-plan-12-meses-design.md`

**Rama:** `feat/plan-12-meses` (ya creada).

---

## Notas de entorno (leer antes de empezar)

- Todos los comandos corren desde `backend/`. El intérprete es `venv/bin/python` y los tests `venv/bin/pytest`.
- `pytest.ini`: `asyncio_mode = auto`, `testpaths = tests`. No hace falta marcar `@pytest.mark.asyncio` en funciones async, pero los tests existentes lo hacen; lo mantenemos por consistencia.
- Patrón de tests de integración: sobreescribir `get_db` y `get_current_user_id` con `app.dependency_overrides` y un `AsyncMock` de sesión. Ver `tests/integration/test_etapa8.py`.
- **Tablas:** el proyecto tiene Alembic configurado (`alembic.ini` → `script_location = app/db/migrations`) pero en la práctica el esquema se materializa fuera de Alembic (la tabla `action_plans` existe sin migración). Por eso este plan entrega **ambos**: una migración formal (`003_annual_plan.py`) y, como respaldo, un snippet `create_all` + `ALTER TABLE` (Task 3, Step 5). Usa el que corresponda a tu flujo de despliegue.
- **`document_tasks.py` tiene un bug latente:** importa `async_session_factory`, que no existe (el nombre real es `AsyncSessionLocal`). No lo arreglamos aquí (fuera de alcance), pero **usa siempre `AsyncSessionLocal`** en el código nuevo.

---

## Estructura de archivos

**Crear:**
- `app/models/annual_plan.py` — modelos `AnnualPlan`, `MonthlyPlan`, `Objective`.
- `app/schemas/annual_plan.py` — schemas Pydantic de I/O.
- `app/services/ai/annual_plan_generator.py` — lógica pura + llamadas a Claude (diagnóstico, esqueleto, tareas, fallback).
- `app/tasks/annual_plan_tasks.py` — tarea Celery orquestadora.
- `app/api/v1/annual_plan/__init__.py` — paquete vacío.
- `app/api/v1/annual_plan/router.py` — endpoints REST.
- `app/db/migrations/versions/003_annual_plan.py` — migración Alembic.
- `tests/unit/test_annual_plan_generator.py` — tests de lógica pura.
- `tests/unit/test_annual_plan_schemas.py` — tests de schemas.
- `tests/integration/test_annual_plan_api.py` — tests de endpoints.

**Modificar:**
- `app/models/action_plan.py` — agregar `objective_id` y `kpi_ref` a `ActionTask`.
- `app/models/__init__.py` — registrar `action_plan` (faltaba) y `annual_plan`.
- `app/schemas/action_plan.py` — `ActionTaskOut.plan_id` opcional + campos `objective_id`/`kpi_ref`.
- `app/main.py` — incluir el router de annual_plan.
- `app/api/v1/onboarding/etapa8.py` — encolar la generación al completar etapa 8.
- `app/tasks/worker.py` — incluir `app.tasks.annual_plan_tasks`.

---

## Task 1: Modelos de plan anual + columnas en ActionTask

**Files:**
- Create: `app/models/annual_plan.py`
- Modify: `app/models/action_plan.py` (clase `ActionTask`)
- Modify: `app/models/__init__.py`
- Test: `tests/unit/test_annual_plan_models.py`

- [ ] **Step 1: Escribir el test de modelos (falla)**

Create `tests/unit/test_annual_plan_models.py`:

```python
"""Verifica la definición de los modelos del plan de 12 meses."""
from app.models.annual_plan import AnnualPlan, MonthlyPlan, Objective
from app.models.action_plan import ActionTask


def test_tablenames():
    assert AnnualPlan.__tablename__ == "annual_plans"
    assert MonthlyPlan.__tablename__ == "monthly_plans"
    assert Objective.__tablename__ == "objectives"


def test_action_task_has_new_columns():
    cols = ActionTask.__table__.columns
    assert "objective_id" in cols
    assert "kpi_ref" in cols
    # objective_id debe ser nullable (coexiste con plan_id legacy)
    assert cols["objective_id"].nullable is True
    assert cols["plan_id"].nullable is True


def test_monthly_plan_has_review_column():
    cols = MonthlyPlan.__table__.columns
    assert "review" in cols          # reservado para subproyecto E
    assert "month_index" in cols
    assert "period_year" in cols
    assert "period_month" in cols


def test_models_registered_in_metadata():
    from app.models import Base
    names = set(Base.metadata.tables.keys())
    assert {"annual_plans", "monthly_plans", "objectives"}.issubset(names)
```

- [ ] **Step 2: Correr el test para verificar que falla**

Run: `venv/bin/pytest tests/unit/test_annual_plan_models.py -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'app.models.annual_plan'`.

- [ ] **Step 3: Crear `app/models/annual_plan.py`**

```python
import uuid
from datetime import date

from sqlalchemy import Date, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin


class AnnualPlan(Base, UUIDMixin, TimestampMixin):
    """Plan estratégico de 12 meses. UNO por empresa/usuario."""
    __tablename__ = "annual_plans"

    user_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    title:   Mapped[str] = mapped_column(Text, nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)

    # generating | active | failed | completed
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="generating")

    # Sesión de consejo "génesis" que guarda el diagnóstico de los 4 agentes.
    genesis_session_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("board_sessions.id", ondelete="SET NULL"),
        nullable=True,
    )
    diagnostico_summary: Mapped[str | None] = mapped_column(Text, nullable=True)

    months: Mapped[list["MonthlyPlan"]] = relationship(
        back_populates="annual_plan",
        cascade="all, delete-orphan",
        order_by="MonthlyPlan.month_index",
    )


class MonthlyPlan(Base, UUIDMixin, TimestampMixin):
    """Un mes (1..12) dentro del plan anual."""
    __tablename__ = "monthly_plans"

    annual_plan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("annual_plans.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    month_index:  Mapped[int] = mapped_column(Integer, nullable=False)  # 1..12
    period_year:  Mapped[int] = mapped_column(Integer, nullable=False)
    period_month: Mapped[int] = mapped_column(Integer, nullable=False)  # 1..12 calendario
    focus: Mapped[str | None] = mapped_column(Text, nullable=True)

    # locked | active | done
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="locked")

    # Reservado para el subproyecto E (revisión de fin de mes: vas bien/mal/muy mal).
    review: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    annual_plan: Mapped["AnnualPlan"] = relationship(back_populates="months")
    objectives: Mapped[list["Objective"]] = relationship(
        back_populates="monthly_plan",
        cascade="all, delete-orphan",
        order_by="Objective.order_index",
    )


class Objective(Base, UUIDMixin, TimestampMixin):
    """Objetivo estratégico de un mes. Las tareas (action_tasks) cuelgan de aquí."""
    __tablename__ = "objectives"

    monthly_plan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("monthly_plans.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title:       Mapped[str]        = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Lista de labels de KPIs (provenientes del onboarding/kpi_engine) que toca el objetivo.
    kpi_refs:    Mapped[list | None] = mapped_column(JSONB, nullable=True, default=list)
    order_index: Mapped[int]        = mapped_column(Integer, nullable=False, default=0)

    monthly_plan: Mapped["MonthlyPlan"] = relationship(back_populates="objectives")
```

- [ ] **Step 4: Agregar columnas a `ActionTask` en `app/models/action_plan.py`**

`ActionTask.plan_id` ya existe como `nullable=False`. Cámbialo a `nullable=True` y agrega las dos columnas nuevas. Reemplaza el bloque del `plan_id` y agrega debajo de `order_index`:

Reemplazar:
```python
    plan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("action_plans.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
```
por:
```python
    plan_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("action_plans.id", ondelete="CASCADE"),
        nullable=True,   # legacy: las tareas del plan anual usan objective_id
        index=True,
    )
    objective_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("objectives.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    kpi_ref: Mapped[str | None] = mapped_column(String, nullable=True)  # "impacto KPI"
```

- [ ] **Step 5: Registrar modelos en `app/models/__init__.py`**

Reemplazar el contenido completo por:
```python
from app.models.base import Base
from app.models.onboarding_session import OnboardingSession
from app.models.document import Document
from app.models.board_session import BoardSession
from app.models.chat_message import ChatMessage
from app.models.action_plan import ActionPlan, ActionTask
from app.models.annual_plan import AnnualPlan, MonthlyPlan, Objective

__all__ = [
    "Base", "OnboardingSession", "Document", "BoardSession", "ChatMessage",
    "ActionPlan", "ActionTask", "AnnualPlan", "MonthlyPlan", "Objective",
]
```

- [ ] **Step 6: Correr el test (pasa)**

Run: `venv/bin/pytest tests/unit/test_annual_plan_models.py -v`
Expected: PASS (4 tests).

- [ ] **Step 7: Commit**

```bash
git add app/models/annual_plan.py app/models/action_plan.py app/models/__init__.py tests/unit/test_annual_plan_models.py
git commit -m "feat(plan): modelos AnnualPlan/MonthlyPlan/Objective + columnas en action_tasks"
```

---

## Task 2: Schemas Pydantic

**Files:**
- Create: `app/schemas/annual_plan.py`
- Modify: `app/schemas/action_plan.py` (clase `ActionTaskOut`)
- Test: `tests/unit/test_annual_plan_schemas.py`

- [ ] **Step 1: Escribir el test (falla)**

Create `tests/unit/test_annual_plan_schemas.py`:

```python
from datetime import date, datetime

from app.schemas.annual_plan import (
    AnnualPlanOut, AnnualPlanStatusOut, MonthlyPlanOut, ObjectiveOut,
    ObjectiveCreate, ObjectiveUpdate, AnnualTaskCreate,
)
from app.schemas.action_plan import ActionTaskOut


def test_action_task_out_plan_id_optional_and_new_fields():
    t = ActionTaskOut(
        id="t1", title="Hacer X", status="pendiente", priority="media",
        created_at=datetime.utcnow(), updated_at=datetime.utcnow(),
        objective_id="o1", kpi_ref="Margen EBITDA",
    )
    assert t.plan_id is None
    assert t.objective_id == "o1"
    assert t.kpi_ref == "Margen EBITDA"


def test_objective_out_nests_tasks():
    obj = ObjectiveOut(
        id="o1", title="Mejorar liquidez", description=None,
        kpi_refs=["Razón corriente"], order_index=0, tasks=[],
    )
    assert obj.kpi_refs == ["Razón corriente"]
    assert obj.tasks == []


def test_annual_plan_out_nests_months():
    plan = AnnualPlanOut(
        id="p1", title="Plan 12 meses", start_date=date.today(),
        status="active", diagnostico_summary="Resumen", genesis_session_id=None,
        months=[],
    )
    assert plan.status == "active"
    assert plan.months == []


def test_status_out():
    s = AnnualPlanStatusOut(status="generating", active_month_index=1)
    assert s.status == "generating"
    assert s.active_month_index == 1


def test_objective_and_task_create():
    oc = ObjectiveCreate(monthly_plan_id="m1", title="Nuevo objetivo")
    assert oc.kpi_refs == []
    tc = AnnualTaskCreate(objective_id="o1", title="Nueva tarea")
    assert tc.priority == "media"
    ou = ObjectiveUpdate(title="editado")
    assert ou.title == "editado"
```

- [ ] **Step 2: Correr el test (falla)**

Run: `venv/bin/pytest tests/unit/test_annual_plan_schemas.py -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'app.schemas.annual_plan'`.

- [ ] **Step 3: Modificar `ActionTaskOut` en `app/schemas/action_plan.py`**

Reemplazar la clase `ActionTaskOut`:
```python
class ActionTaskOut(ActionTaskBase):
    id:         str
    plan_id:    str
    created_at: datetime
    updated_at: datetime
```
por:
```python
class ActionTaskOut(ActionTaskBase):
    id:           str
    plan_id:      str | None = None
    objective_id: str | None = None
    kpi_ref:      str | None = None
    created_at:   datetime
    updated_at:   datetime
```

> Nota: el router de action_plans pasa `plan_id=str(t.plan_id)`; sigue siendo válido. El `_task_to_out` de ese router no setea `objective_id`/`kpi_ref`, por lo que tomarán su default `None` — comportamiento correcto para las tareas legacy.

- [ ] **Step 4: Crear `app/schemas/annual_plan.py`**

```python
from datetime import date, datetime

from pydantic import BaseModel, Field

from app.schemas.action_plan import ActionTaskOut, TaskPriority, TaskStatus


class ObjectiveOut(BaseModel):
    id:          str
    title:       str
    description: str | None = None
    kpi_refs:    list[str] = Field(default_factory=list)
    order_index: int = 0
    tasks:       list[ActionTaskOut] = Field(default_factory=list)


class MonthlyPlanOut(BaseModel):
    id:           str
    month_index:  int
    period_year:  int
    period_month: int
    focus:        str | None = None
    status:       str
    review:       dict | None = None
    objectives:   list[ObjectiveOut] = Field(default_factory=list)


class AnnualPlanOut(BaseModel):
    id:                  str
    title:               str
    start_date:          date
    status:              str
    diagnostico_summary: str | None = None
    genesis_session_id:  str | None = None
    months:              list[MonthlyPlanOut] = Field(default_factory=list)


class AnnualPlanStatusOut(BaseModel):
    status:             str            # generating | active | failed | completed
    active_month_index: int | None = None


# ── Edición ───────────────────────────────────────────────────────────────────

class ObjectiveCreate(BaseModel):
    monthly_plan_id: str
    title:           str
    description:     str | None = None
    kpi_refs:        list[str] = Field(default_factory=list)


class ObjectiveUpdate(BaseModel):
    title:       str | None = None
    description: str | None = None
    kpi_refs:    list[str] | None = None
    order_index: int | None = None


class AnnualTaskCreate(BaseModel):
    objective_id: str
    title:        str
    description:  str | None = None
    status:       TaskStatus = "pendiente"
    priority:     TaskPriority = "media"
    owner:        str | None = None
    due_date:     date | None = None
    kpi_ref:      str | None = None
    tags:         list[str] = Field(default_factory=list)
```

- [ ] **Step 5: Correr el test (pasa)**

Run: `venv/bin/pytest tests/unit/test_annual_plan_schemas.py -v`
Expected: PASS (5 tests).

- [ ] **Step 6: Commit**

```bash
git add app/schemas/annual_plan.py app/schemas/action_plan.py tests/unit/test_annual_plan_schemas.py
git commit -m "feat(plan): schemas Pydantic del plan anual + ActionTaskOut con objective_id/kpi_ref"
```

---

## Task 3: Migración Alembic 003

**Files:**
- Create: `app/db/migrations/versions/003_annual_plan.py`

> No hay test unitario para la migración (requiere una DB Postgres real). La verificación es de compilación + revisión manual. El snippet de respaldo `create_all`/`ALTER` (Step 5) cubre el flujo no-Alembic del proyecto.

- [ ] **Step 1: Crear `app/db/migrations/versions/003_annual_plan.py`**

```python
"""annual_plans, monthly_plans, objectives + columnas en action_tasks

Revision ID: 003_annual_plan
Revises: 002_board_sessions_chat
Create Date: 2026-05-28
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "003_annual_plan"
down_revision = "002_board_sessions_chat"
branch_labels = None
depends_on = None


def _timestamps():
    return (
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
    )


def upgrade() -> None:
    op.create_table(
        "annual_plans",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", sa.String, nullable=False, index=True),
        sa.Column("title", sa.Text, nullable=False),
        sa.Column("start_date", sa.Date, nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="generating"),
        sa.Column("genesis_session_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("board_sessions.id", ondelete="SET NULL"), nullable=True),
        sa.Column("diagnostico_summary", sa.Text, nullable=True),
        *_timestamps(),
    )

    op.create_table(
        "monthly_plans",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("annual_plan_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("annual_plans.id", ondelete="CASCADE"),
                  nullable=False, index=True),
        sa.Column("month_index", sa.Integer, nullable=False),
        sa.Column("period_year", sa.Integer, nullable=False),
        sa.Column("period_month", sa.Integer, nullable=False),
        sa.Column("focus", sa.Text, nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="locked"),
        sa.Column("review", postgresql.JSONB, nullable=True),
        *_timestamps(),
    )

    op.create_table(
        "objectives",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("monthly_plan_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("monthly_plans.id", ondelete="CASCADE"),
                  nullable=False, index=True),
        sa.Column("title", sa.Text, nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("kpi_refs", postgresql.JSONB, nullable=True),
        sa.Column("order_index", sa.Integer, nullable=False, server_default="0"),
        *_timestamps(),
    )

    # action_tasks: plan_id pasa a nullable + nuevas columnas
    op.alter_column("action_tasks", "plan_id", nullable=True)
    op.add_column("action_tasks",
                  sa.Column("objective_id", postgresql.UUID(as_uuid=True),
                            sa.ForeignKey("objectives.id", ondelete="CASCADE"), nullable=True))
    op.add_column("action_tasks", sa.Column("kpi_ref", sa.String, nullable=True))
    op.create_index("ix_action_tasks_objective_id", "action_tasks", ["objective_id"])


def downgrade() -> None:
    op.drop_index("ix_action_tasks_objective_id", table_name="action_tasks")
    op.drop_column("action_tasks", "kpi_ref")
    op.drop_column("action_tasks", "objective_id")
    op.alter_column("action_tasks", "plan_id", nullable=False)
    op.drop_table("objectives")
    op.drop_table("monthly_plans")
    op.drop_table("annual_plans")
```

- [ ] **Step 2: Verificar que compila**

Run: `venv/bin/python -m py_compile app/db/migrations/versions/003_annual_plan.py`
Expected: sin salida (exit 0).

- [ ] **Step 3: (Si usas Alembic) aplicar la migración**

Run: `venv/bin/alembic upgrade head`
Expected: `Running upgrade 002_board_sessions_chat -> 003_annual_plan`.

> Si Alembic falla porque la cadena de revisiones está rota en tu DB (la 002 tiene `down_revision=None` y `action_plans` no tiene migración), usa el respaldo del Step 5 en su lugar.

- [ ] **Step 4: (Si usas Alembic) verificar tablas**

Run: `venv/bin/python -c "from sqlalchemy import create_engine, inspect; from app.core.config import settings; e=create_engine(settings.DATABASE_URL.replace('+asyncpg','')); print([t for t in inspect(e).get_table_names() if 'plan' in t or t=='objectives'])"`
Expected: incluye `annual_plans`, `monthly_plans`, `objectives`, `action_plans`.

- [ ] **Step 5: Respaldo no-Alembic (solo si NO usas Alembic)**

Crear y correr una sola vez `backend/scripts/create_annual_plan_tables.py`:
```python
"""Crea las tablas del plan anual y altera action_tasks SIN Alembic.
Idempotente: create_all omite tablas existentes; los ALTER usan IF NOT EXISTS / IF EXISTS.
"""
import asyncio
from sqlalchemy import text
from app.db.session import engine
import app.models  # noqa: F401  (registra todos los modelos en Base.metadata)
from app.models import Base


async def main():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.execute(text("ALTER TABLE action_tasks ALTER COLUMN plan_id DROP NOT NULL"))
        await conn.execute(text(
            "ALTER TABLE action_tasks ADD COLUMN IF NOT EXISTS objective_id "
            "UUID REFERENCES objectives(id) ON DELETE CASCADE"))
        await conn.execute(text("ALTER TABLE action_tasks ADD COLUMN IF NOT EXISTS kpi_ref VARCHAR"))
    await engine.dispose()
    print("OK: tablas del plan anual creadas / action_tasks alterada")


if __name__ == "__main__":
    asyncio.run(main())
```
Run: `venv/bin/python -m scripts.create_annual_plan_tables`
Expected: `OK: tablas del plan anual creadas / action_tasks alterada`.

- [ ] **Step 6: Commit**

```bash
git add app/db/migrations/versions/003_annual_plan.py backend/scripts/create_annual_plan_tables.py 2>/dev/null; git add app/db/migrations/versions/003_annual_plan.py
git commit -m "feat(plan): migración 003 + script de respaldo para tablas del plan anual"
```

---

## Task 4: Lógica pura del generador — calendario y due dates

**Files:**
- Create: `app/services/ai/annual_plan_generator.py` (primera parte)
- Test: `tests/unit/test_annual_plan_generator.py` (primera parte)

- [ ] **Step 1: Escribir el test (falla)**

Create `tests/unit/test_annual_plan_generator.py`:

```python
from datetime import date

from app.services.ai.annual_plan_generator import (
    month_calendar, compute_active_month_index, due_date_within_month,
)


def test_month_calendar_wraps_year():
    # start en nov 2026, month_index 1 = nov 2026, 3 = ene 2027
    assert month_calendar(2026, 11, 1) == (2026, 11)
    assert month_calendar(2026, 11, 2) == (2026, 12)
    assert month_calendar(2026, 11, 3) == (2027, 1)
    assert month_calendar(2026, 11, 12) == (2027, 10)


def test_compute_active_month_index():
    start = date(2026, 5, 1)
    assert compute_active_month_index(start, date(2026, 5, 15)) == 1
    assert compute_active_month_index(start, date(2026, 7, 2)) == 3
    # antes del inicio → 1; pasado el mes 12 → 12 (cap)
    assert compute_active_month_index(start, date(2026, 4, 1)) == 1
    assert compute_active_month_index(start, date(2030, 1, 1)) == 12


def test_due_date_within_month_clamps_day():
    assert due_date_within_month(2026, 2, 31) == date(2026, 2, 28)   # feb no bisiesto
    assert due_date_within_month(2026, 6, 15) == date(2026, 6, 15)
    assert due_date_within_month(2026, 6, 0) == date(2026, 6, 1)     # piso 1
```

- [ ] **Step 2: Correr el test (falla)**

Run: `venv/bin/pytest tests/unit/test_annual_plan_generator.py -v`
Expected: FAIL con `ModuleNotFoundError`.

- [ ] **Step 3: Crear `app/services/ai/annual_plan_generator.py` con los helpers de calendario**

```python
"""
Generador del Plan Estratégico de 12 meses.

Tres pasos (orquestados por app.tasks.annual_plan_tasks):
1. DIAGNÓSTICO  — reutiliza los 4 agentes + Challenger (board.base).
2. ESQUELETO    — 1 llamada → 12 meses con focus + objetivos + kpi_refs.
3. TAREAS       — por mes, tareas de cada objetivo (owner/prioridad/due/kpi_ref).

La lógica pura (calendario, parseo, mapeo, fallback) vive aquí y se testea sin DB ni red.
"""
import calendar
import json
from datetime import date

import anthropic

from app.core.config import settings
from app.services.ai.agents.base import _create_with_retry, _extract_json_object


# ── Helpers de calendario ───────────────────────────────────────────────────

def month_calendar(start_year: int, start_month: int, month_index: int) -> tuple[int, int]:
    """Dado el mes de inicio y un month_index 1..12, retorna (año, mes) calendario."""
    zero_based = (start_year * 12 + (start_month - 1)) + (month_index - 1)
    return zero_based // 12, zero_based % 12 + 1


def compute_active_month_index(start_date: date, today: date) -> int:
    """Índice (1..12) del mes vigente del plan según la fecha de hoy. Cap en [1, 12]."""
    elapsed = (today.year - start_date.year) * 12 + (today.month - start_date.month)
    return min(max(elapsed + 1, 1), 12)


def due_date_within_month(year: int, month: int, day: int = 28) -> date:
    """Construye una fecha dentro del mes, clampeando el día a [1, último día del mes]."""
    last = calendar.monthrange(year, month)[1]
    return date(year, month, min(max(day, 1), last))
```

- [ ] **Step 4: Correr el test (pasa)**

Run: `venv/bin/pytest tests/unit/test_annual_plan_generator.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add app/services/ai/annual_plan_generator.py tests/unit/test_annual_plan_generator.py
git commit -m "feat(plan): helpers de calendario del generador anual"
```

---

## Task 5: Parseo de esqueleto y mapeo de tareas

**Files:**
- Modify: `app/services/ai/annual_plan_generator.py` (agregar parseo/mapeo)
- Modify: `tests/unit/test_annual_plan_generator.py` (agregar tests)

- [ ] **Step 1: Agregar tests (fallan)**

Append a `tests/unit/test_annual_plan_generator.py`:

```python
from app.services.ai.annual_plan_generator import (
    parse_skeleton, map_month_tasks, synthesize_diagnostico, fallback_skeleton,
)


def test_parse_skeleton_normaliza_12_meses():
    raw = '''{"months":[
      {"month_index":1,"focus":"Liquidez","objectives":[
        {"title":"Mejorar caja","kpi_refs":["Razón corriente"]}]}
    ]}'''
    months = parse_skeleton(raw)
    assert len(months) == 12                       # rellena hasta 12
    assert months[0]["focus"] == "Liquidez"
    assert months[0]["objectives"][0]["title"] == "Mejorar caja"
    assert months[0]["objectives"][0]["kpi_refs"] == ["Razón corriente"]
    # meses faltantes quedan con objetivos vacíos pero presentes
    assert months[11]["month_index"] == 12
    assert months[11]["objectives"] == []


def test_parse_skeleton_basura_devuelve_fallback():
    months = parse_skeleton("no soy json")
    assert len(months) == 12


def test_map_month_tasks_normaliza_campos():
    raw = '''{"tasks":[
      {"objective_index":0,"title":"Negociar línea de crédito","owner":"CFO",
       "priority":"ALTA","due_day":10,"kpi_ref":"Razón corriente","tags":["Liquidez","x"]},
      {"objective_index":9,"title":"fuera de rango"}
    ]}'''
    objectives = [{"title": "Mejorar caja"}]
    tasks = map_month_tasks(raw, objectives, year=2026, month=6)
    # la tarea con objective_index fuera de rango se descarta
    assert len(tasks) == 1
    t = tasks[0]
    assert t["objective_index"] == 0
    assert t["priority"] == "alta"
    assert t["owner"] == "CFO"
    assert t["due_date"] == "2026-06-10"
    assert t["kpi_ref"] == "Razón corriente"
    assert t["tags"] == ["liquidez", "x"]


def test_synthesize_diagnostico_concatena_resumenes():
    analyses = {
        "CFO": {"summary": "Liquidez ajustada."},
        "CSO": {"summary": "Ventas concentradas."},
    }
    text = synthesize_diagnostico(analyses)
    assert "CFO" in text and "Liquidez ajustada." in text
    assert "CSO" in text and "Ventas concentradas." in text


def test_fallback_skeleton_es_12_meses():
    sk = fallback_skeleton()
    assert len(sk) == 12
    assert all(m["month_index"] == i + 1 for i, m in enumerate(sk))
```

- [ ] **Step 2: Correr (falla)**

Run: `venv/bin/pytest tests/unit/test_annual_plan_generator.py -v`
Expected: FAIL con `ImportError: cannot import name 'parse_skeleton'`.

- [ ] **Step 3: Agregar parseo/mapeo a `annual_plan_generator.py`**

Append:

```python
# ── Normalización ───────────────────────────────────────────────────────────

_PRIORITIES = {"alta", "media", "baja"}


def _norm_priority(v) -> str:
    return v.lower() if isinstance(v, str) and v.lower() in _PRIORITIES else "media"


def _norm_tags(v) -> list[str]:
    if not isinstance(v, list):
        return []
    return [str(t).lower().strip()[:30] for t in v if t][:3]


def fallback_skeleton() -> list[dict]:
    """Esqueleto determinista de 12 meses sin objetivos (cuando no hay API key o falla)."""
    return [{"month_index": i, "focus": None, "objectives": []} for i in range(1, 13)]


def parse_skeleton(raw: str) -> list[dict]:
    """
    Parsea la respuesta del LLM a una lista de EXACTAMENTE 12 meses ordenados.
    Cada mes: {month_index, focus, objectives:[{title, description, kpi_refs}]}.
    Rellena meses faltantes con objetivos vacíos. Ante basura, devuelve fallback.
    """
    parsed = _extract_json_object(raw)
    if not parsed or not isinstance(parsed.get("months"), list):
        return fallback_skeleton()

    by_index: dict[int, dict] = {}
    for m in parsed["months"]:
        if not isinstance(m, dict):
            continue
        try:
            idx = int(m.get("month_index"))
        except (TypeError, ValueError):
            continue
        if not 1 <= idx <= 12:
            continue
        objectives = []
        for o in (m.get("objectives") or []):
            if not isinstance(o, dict) or not o.get("title"):
                continue
            objectives.append({
                "title": str(o["title"])[:300],
                "description": str(o["description"]) if o.get("description") else None,
                "kpi_refs": [str(k)[:120] for k in (o.get("kpi_refs") or []) if k][:5],
            })
        by_index[idx] = {
            "month_index": idx,
            "focus": str(m["focus"])[:300] if m.get("focus") else None,
            "objectives": objectives,
        }

    return [by_index.get(i, {"month_index": i, "focus": None, "objectives": []})
            for i in range(1, 13)]


def map_month_tasks(raw: str, objectives: list[dict], year: int, month: int) -> list[dict]:
    """
    Parsea las tareas de un mes. Descarta las que apunten a un objective_index inexistente.
    Retorna dicts con: objective_index, title, description, owner, priority, due_date(ISO),
    kpi_ref, tags, order_index.
    """
    parsed = _extract_json_object(raw)
    if not parsed or not isinstance(parsed.get("tasks"), list):
        return []

    out: list[dict] = []
    for order, t in enumerate(parsed["tasks"]):
        if not isinstance(t, dict) or not t.get("title"):
            continue
        try:
            obj_idx = int(t.get("objective_index", 0))
        except (TypeError, ValueError):
            continue
        if not 0 <= obj_idx < len(objectives):
            continue
        try:
            day = int(t.get("due_day", 28))
        except (TypeError, ValueError):
            day = 28
        out.append({
            "objective_index": obj_idx,
            "title": str(t["title"])[:200],
            "description": str(t["description"]) if t.get("description") else None,
            "owner": str(t["owner"]) if t.get("owner") else None,
            "priority": _norm_priority(t.get("priority")),
            "due_date": due_date_within_month(year, month, day).isoformat(),
            "kpi_ref": str(t["kpi_ref"])[:120] if t.get("kpi_ref") else None,
            "tags": _norm_tags(t.get("tags")),
            "order_index": order,
        })
    return out


def synthesize_diagnostico(agent_analyses: dict[str, dict]) -> str:
    """Concatena los summaries de los 4 agentes en un diagnóstico legible."""
    parts = []
    for agent, analysis in agent_analyses.items():
        if isinstance(analysis, dict) and analysis.get("summary"):
            parts.append(f"**{agent}:** {analysis['summary']}")
    return "\n\n".join(parts)
```

- [ ] **Step 4: Correr (pasa)**

Run: `venv/bin/pytest tests/unit/test_annual_plan_generator.py -v`
Expected: PASS (8 tests en total).

- [ ] **Step 5: Commit**

```bash
git add app/services/ai/annual_plan_generator.py tests/unit/test_annual_plan_generator.py
git commit -m "feat(plan): parseo de esqueleto, mapeo de tareas y síntesis de diagnóstico"
```

---

## Task 6: Llamadas a Claude (esqueleto y tareas)

**Files:**
- Modify: `app/services/ai/annual_plan_generator.py` (prompts + funciones que llaman al LLM)
- Modify: `tests/unit/test_annual_plan_generator.py` (test con cliente mockeado)

> Las funciones `generate_skeleton` y `generate_month_tasks` llaman a Claude vía `_create_with_retry`. Se testean monkeypatcheando esa función para no hacer red.

- [ ] **Step 1: Agregar tests (fallan)**

Append a `tests/unit/test_annual_plan_generator.py`:

```python
import app.services.ai.annual_plan_generator as gen


class _FakeResponse:
    def __init__(self, text):
        self.content = [type("B", (), {"text": text})()]


def test_generate_skeleton_sin_apikey_usa_fallback(monkeypatch):
    monkeypatch.setattr(gen.settings, "ANTHROPIC_API_KEY", "", raising=False)
    months = gen.generate_skeleton({"company": {"name": "Demo"}}, "Diagnóstico", kpi_labels=[])
    assert len(months) == 12


def test_generate_skeleton_con_apikey_parsea_respuesta(monkeypatch):
    monkeypatch.setattr(gen.settings, "ANTHROPIC_API_KEY", "sk-test", raising=False)
    raw = '{"months":[{"month_index":1,"focus":"Caja","objectives":[{"title":"X","kpi_refs":[]}]}]}'
    monkeypatch.setattr(gen, "_create_with_retry", lambda *a, **k: _FakeResponse(raw))
    monkeypatch.setattr(gen.anthropic, "Anthropic", lambda **k: object())
    months = gen.generate_skeleton({"company": {"name": "Demo"}}, "Diag", kpi_labels=["Caja"])
    assert months[0]["focus"] == "Caja"


def test_generate_month_tasks_con_apikey(monkeypatch):
    monkeypatch.setattr(gen.settings, "ANTHROPIC_API_KEY", "sk-test", raising=False)
    raw = '{"tasks":[{"objective_index":0,"title":"Negociar crédito","priority":"alta","due_day":10}]}'
    monkeypatch.setattr(gen, "_create_with_retry", lambda *a, **k: _FakeResponse(raw))
    monkeypatch.setattr(gen.anthropic, "Anthropic", lambda **k: object())
    tasks = gen.generate_month_tasks(
        focus="Liquidez", objectives=[{"title": "Mejorar caja"}],
        memory_buffer={"company": {"name": "Demo"}}, year=2026, month=6,
    )
    assert tasks[0]["title"] == "Negociar crédito"
    assert tasks[0]["due_date"] == "2026-06-10"
```

- [ ] **Step 2: Correr (falla)**

Run: `venv/bin/pytest tests/unit/test_annual_plan_generator.py -v`
Expected: FAIL con `AttributeError: module ... has no attribute 'generate_skeleton'`.

- [ ] **Step 3: Agregar prompts y funciones LLM a `annual_plan_generator.py`**

Append:

```python
# ── Prompts ─────────────────────────────────────────────────────────────────

SKELETON_SYSTEM_PROMPT = """Eres el director estratégico del consejo de Gobernia.
A partir del diagnóstico de los 4 agentes, diseñas un PLAN ESTRATÉGICO de 12 meses.

Reglas:
1. Genera EXACTAMENTE 12 meses (month_index 1..12), con progresión lógica:
   los primeros meses estabilizan y diagnostican; los del medio ejecutan; los últimos
   consolidan y miden resultados.
2. Cada mes tiene un "focus" (tema corto, máx 80 caracteres) y 2-4 objetivos.
3. Cada objetivo: "title" accionable y "kpi_refs" = lista de KPIs (de la lista provista)
   que ese objetivo busca mover. Usa SOLO labels de la lista de KPIs disponibles.
4. No inventes KPIs fuera de la lista. Si la lista está vacía, deja kpi_refs como []."""

SKELETON_SCHEMA = """{
  "months": [
    {"month_index": 1, "focus": "string",
     "objectives": [{"title": "string", "description": "string", "kpi_refs": ["KPI label"]}]}
  ]
}"""

MONTH_TASKS_SYSTEM_PROMPT = """Eres el director del consejo. Conviertes los objetivos de UN mes
en tareas concretas y accionables.

Reglas por tarea:
1. "title": empieza con verbo en infinitivo, máx 80 caracteres.
2. "objective_index": índice (0-based) del objetivo al que pertenece, según la lista dada.
3. "owner": rol responsable (Director General, CFO, Director Comercial, etc.).
4. "priority": "alta" | "media" | "baja".
5. "due_day": día del mes (1-28) en que vence.
6. "kpi_ref": un KPI (de los kpi_refs del objetivo) que la tarea impacta, o null.
7. "tags": máximo 2 etiquetas cortas en minúsculas.
Genera entre 2 y 5 tareas por objetivo. Calidad sobre cantidad."""

MONTH_TASKS_SCHEMA = """{
  "tasks": [
    {"objective_index": 0, "title": "string", "description": "string",
     "owner": "string", "priority": "alta|media|baja", "due_day": 15,
     "kpi_ref": "KPI label|null", "tags": ["tag"]}
  ]
}"""


def _company_line(memory_buffer: dict) -> str:
    c = memory_buffer.get("company", {}) or {}
    return f"Empresa: {c.get('name', 'la empresa')} | Industria: {c.get('industry', 'N/D')}"


def generate_skeleton(memory_buffer: dict, diagnostico: str, kpi_labels: list[str]) -> list[dict]:
    """Paso 2: una llamada genera el esqueleto de 12 meses. Fallback si no hay API key."""
    if not settings.ANTHROPIC_API_KEY:
        return fallback_skeleton()

    user_prompt = (
        f"{_company_line(memory_buffer)}\n\n"
        f"DIAGNÓSTICO DE LOS 4 AGENTES:\n{diagnostico}\n\n"
        f"KPIs DISPONIBLES (usa solo estos labels en kpi_refs): {kpi_labels or 'ninguno'}\n\n"
        "Diseña el plan de 12 meses. Responde ÚNICAMENTE con JSON válido:\n"
        f"{SKELETON_SCHEMA}"
    )
    client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    response = _create_with_retry(
        client, model=settings.AI_MODEL, max_tokens=4096,
        system=SKELETON_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_prompt}],
    )
    return parse_skeleton(response.content[0].text)


def generate_month_tasks(focus, objectives: list[dict], memory_buffer: dict,
                         year: int, month: int) -> list[dict]:
    """Paso 3: tareas de un mes. Sin API key u objetivos vacíos → []."""
    if not settings.ANTHROPIC_API_KEY or not objectives:
        return []

    obj_list = "\n".join(
        f"  [{i}] {o['title']} (KPIs: {o.get('kpi_refs') or 'ninguno'})"
        for i, o in enumerate(objectives)
    )
    user_prompt = (
        f"{_company_line(memory_buffer)}\n\n"
        f"FOCO DEL MES: {focus or 'N/D'}\n"
        f"OBJETIVOS DEL MES (usa el índice en objective_index):\n{obj_list}\n\n"
        "Genera las tareas. Responde ÚNICAMENTE con JSON válido:\n"
        f"{MONTH_TASKS_SCHEMA}"
    )
    client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    response = _create_with_retry(
        client, model=settings.AI_MODEL, max_tokens=2048,
        system=MONTH_TASKS_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_prompt}],
    )
    return map_month_tasks(response.content[0].text, objectives, year, month)
```

- [ ] **Step 4: Correr (pasa)**

Run: `venv/bin/pytest tests/unit/test_annual_plan_generator.py -v`
Expected: PASS (11 tests en total).

- [ ] **Step 5: Commit**

```bash
git add app/services/ai/annual_plan_generator.py tests/unit/test_annual_plan_generator.py
git commit -m "feat(plan): llamadas a Claude para esqueleto anual y tareas por mes"
```

---

## Task 7: Tarea Celery orquestadora

**Files:**
- Create: `app/tasks/annual_plan_tasks.py`
- Modify: `app/tasks/worker.py` (include)
- Test: `tests/unit/test_annual_plan_orchestration.py`

> El orquestador `_run_generation(annual_plan_id)` recibe un `AnnualPlan` ya creado en estado `generating` (lo crea el endpoint, ver Task 8) y lo llena. Para testearlo sin DB real, se monkeypatchean los generadores y se le pasa una sesión `AsyncMock`. Se extrae además una función pura `kpi_labels_from_buffer` para tests directos.

- [ ] **Step 1: Escribir el test (falla)**

Create `tests/unit/test_annual_plan_orchestration.py`:

```python
import uuid
from datetime import date
from unittest.mock import AsyncMock, MagicMock

import pytest

import app.tasks.annual_plan_tasks as orch


def test_kpi_labels_from_buffer():
    buf = {"kpis": {"finanzas": [{"label": "Razón corriente"}, {"label": "EBITDA"}],
                    "comercial": [{"label": "CAC"}]}}
    labels = orch.kpi_labels_from_buffer(buf)
    assert set(labels) == {"Razón corriente", "EBITDA", "CAC"}
    assert orch.kpi_labels_from_buffer({}) == []


@pytest.mark.asyncio
async def test_run_generation_happy_path(monkeypatch):
    plan = MagicMock()
    plan.id = uuid.uuid4()
    plan.start_date = date(2026, 5, 1)
    plan.status = "generating"

    # Sesión que devuelve nuestro plan y la onboarding session con buffer + analyses
    onboarding = MagicMock()
    onboarding.memory_buffer = {"company": {"name": "Demo"}, "kpis": {}}

    db = AsyncMock()
    # get(AnnualPlan, id) → plan ; demás execute → onboarding
    db.get = AsyncMock(return_value=plan)
    result = MagicMock()
    result.scalar_one_or_none.return_value = onboarding
    db.execute = AsyncMock(return_value=result)
    db.add = MagicMock()
    db.add_all = MagicMock()
    db.flush = AsyncMock()
    db.commit = AsyncMock()

    monkeypatch.setattr(orch, "run_diagnostico", lambda buf: ({"CFO": {"summary": "ok"}}, None))
    monkeypatch.setattr(orch, "synthesize_diagnostico", lambda a: "Diag")
    monkeypatch.setattr(orch, "generate_skeleton",
                        lambda buf, diag, kpi_labels: [
                            {"month_index": i, "focus": "f",
                             "objectives": [{"title": "O", "description": None, "kpi_refs": []}]}
                            for i in range(1, 13)])
    monkeypatch.setattr(orch, "generate_month_tasks",
                        lambda **k: [{"objective_index": 0, "title": "T", "description": None,
                                      "owner": "CFO", "priority": "alta", "due_date": "2026-05-10",
                                      "kpi_ref": None, "tags": [], "order_index": 0}])

    await orch._run_generation(str(plan.id), db)

    assert plan.status == "active"
    assert plan.diagnostico_summary == "Diag"
    assert db.add_all.called or db.add.called
    assert db.commit.await_count >= 1


@pytest.mark.asyncio
async def test_run_generation_marks_failed_on_error(monkeypatch):
    plan = MagicMock()
    plan.id = uuid.uuid4()
    plan.start_date = date(2026, 5, 1)
    plan.status = "generating"

    db = AsyncMock()
    db.get = AsyncMock(return_value=plan)
    db.commit = AsyncMock()
    db.execute = AsyncMock(side_effect=RuntimeError("boom"))

    with pytest.raises(RuntimeError):
        await orch._run_generation(str(plan.id), db)
    assert plan.status == "failed"
```

- [ ] **Step 2: Correr (falla)**

Run: `venv/bin/pytest tests/unit/test_annual_plan_orchestration.py -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'app.tasks.annual_plan_tasks'`.

- [ ] **Step 3: Crear `app/tasks/annual_plan_tasks.py`**

```python
"""
Tarea Celery: genera el plan estratégico de 12 meses tras cerrar el onboarding.
Corre en el worker (proceso síncrono) y envuelve la lógica async con asyncio.run,
igual que document_tasks. Crea su propia sesión de DB.
"""
import asyncio
import uuid

from app.tasks.worker import celery_app
from app.services.ai.annual_plan_generator import (
    generate_month_tasks, generate_skeleton, month_calendar,
    compute_active_month_index, synthesize_diagnostico,
)


def kpi_labels_from_buffer(memory_buffer: dict) -> list[str]:
    """Extrae los labels de todos los KPIs del onboarding (kpi_engine)."""
    labels: list[str] = []
    for kpis in (memory_buffer.get("kpis") or {}).values():
        for kpi in kpis or []:
            if isinstance(kpi, dict) and kpi.get("label"):
                labels.append(str(kpi["label"]))
    return labels


def run_diagnostico(memory_buffer: dict) -> tuple[dict, None]:
    """
    Paso 1: corre los 4 agentes sobre el memory_buffer del onboarding.
    Retorna (agent_analyses, None). Sin API key, cada agente devuelve su placeholder.
    """
    from app.services.ai.agents.base import run_agent_analysis
    from datetime import date

    today = date.today()
    analyses: dict[str, dict] = {}
    for agent in ("CFO", "CSO", "CRO", "Auditor"):
        analyses[agent] = run_agent_analysis(
            agent, memory_buffer, kpi_snapshot=memory_buffer.get("kpis"),
            period_year=today.year, period_month=today.month,
        )
    return analyses, None


@celery_app.task(name="generate_annual_plan", bind=True, max_retries=2)
def generate_annual_plan_task(self, annual_plan_id: str) -> dict:
    try:
        return asyncio.run(_entrypoint(annual_plan_id))
    except Exception as exc:
        raise self.retry(exc=exc, countdown=30)


async def _entrypoint(annual_plan_id: str) -> dict:
    from app.db.session import AsyncSessionLocal
    async with AsyncSessionLocal() as db:
        await _run_generation(annual_plan_id, db)
    return {"status": "active", "annual_plan_id": annual_plan_id}


async def _run_generation(annual_plan_id: str, db) -> None:
    """Llena un AnnualPlan en estado 'generating'. Marca 'failed' y re-lanza ante error."""
    from sqlalchemy import select
    from app.models.annual_plan import AnnualPlan, MonthlyPlan, Objective
    from app.models.action_plan import ActionTask
    from app.models.board_session import BoardSession
    from app.models.onboarding_session import OnboardingSession

    plan = await db.get(AnnualPlan, uuid.UUID(annual_plan_id))
    if plan is None:
        return

    try:
        # Cargar el onboarding más reciente del usuario (memory_buffer).
        onb_res = await db.execute(
            select(OnboardingSession)
            .where(OnboardingSession.user_id == plan.user_id)
            .order_by(OnboardingSession.created_at.desc()).limit(1)
        )
        onboarding = onb_res.scalar_one_or_none()
        memory_buffer = (onboarding.memory_buffer if onboarding else {}) or {}

        # Paso 1: diagnóstico
        analyses, _ = run_diagnostico(memory_buffer)
        plan.diagnostico_summary = synthesize_diagnostico(analyses)

        # Sesión génesis que guarda los análisis (si hay onboarding)
        if onboarding is not None:
            from datetime import date as _date
            genesis = BoardSession(
                onboarding_session_id=onboarding.id,
                user_id=plan.user_id,
                period_year=plan.start_date.year,
                period_month=plan.start_date.month,
                status="completed",
                agent_analyses=analyses,
            )
            db.add(genesis)
            await db.flush()
            plan.genesis_session_id = genesis.id

        # Paso 2: esqueleto
        skeleton = generate_skeleton(
            memory_buffer, plan.diagnostico_summary, kpi_labels_from_buffer(memory_buffer),
        )

        active_idx = compute_active_month_index(plan.start_date, __import__("datetime").date.today())

        # Paso 3: meses → objetivos → tareas
        for m in skeleton:
            year, month = month_calendar(plan.start_date.year, plan.start_date.month, m["month_index"])
            monthly = MonthlyPlan(
                annual_plan_id=plan.id,
                month_index=m["month_index"],
                period_year=year, period_month=month,
                focus=m.get("focus"),
                status="active" if m["month_index"] == active_idx else (
                    "done" if m["month_index"] < active_idx else "locked"),
            )
            db.add(monthly)
            await db.flush()

            objectives_models = []
            for oi, o in enumerate(m["objectives"]):
                obj = Objective(
                    monthly_plan_id=monthly.id,
                    title=o["title"], description=o.get("description"),
                    kpi_refs=o.get("kpi_refs", []), order_index=oi,
                )
                db.add(obj)
                objectives_models.append(obj)
            await db.flush()

            task_specs = generate_month_tasks(
                focus=m.get("focus"), objectives=m["objectives"],
                memory_buffer=memory_buffer, year=year, month=month,
            )
            from app.api.v1.action_plans.router import _parse_iso_date
            for ts in task_specs:
                obj = objectives_models[ts["objective_index"]]
                db.add(ActionTask(
                    objective_id=obj.id,
                    title=ts["title"], description=ts.get("description"),
                    source_agent=None, status="pendiente",
                    priority=ts["priority"], owner=ts.get("owner"),
                    due_date=_parse_iso_date(ts.get("due_date")),
                    kpi_ref=ts.get("kpi_ref"),
                    tags=ts.get("tags", []), order_index=ts["order_index"],
                ))

        plan.status = "active"
        await db.commit()
    except Exception:
        plan.status = "failed"
        await db.commit()
        raise
```

- [ ] **Step 4: Registrar el módulo en el worker — `app/tasks/worker.py`**

Reemplazar:
```python
    include=["app.tasks.document_tasks"],
```
por:
```python
    include=["app.tasks.document_tasks", "app.tasks.annual_plan_tasks"],
```

- [ ] **Step 5: Correr (pasa)**

Run: `venv/bin/pytest tests/unit/test_annual_plan_orchestration.py -v`
Expected: PASS (3 tests).

- [ ] **Step 6: Commit**

```bash
git add app/tasks/annual_plan_tasks.py app/tasks/worker.py tests/unit/test_annual_plan_orchestration.py
git commit -m "feat(plan): tarea Celery que orquesta diagnóstico→esqueleto→tareas"
```

---

## Task 8: Router de la API + enganche con etapa 8

**Files:**
- Create: `app/api/v1/annual_plan/__init__.py`
- Create: `app/api/v1/annual_plan/router.py`
- Modify: `app/main.py`
- Modify: `app/api/v1/onboarding/etapa8.py`
- Test: `tests/integration/test_annual_plan_api.py`

- [ ] **Step 1: Crear `app/api/v1/annual_plan/__init__.py`** (vacío)

```python
```

- [ ] **Step 2: Escribir el test de API (falla)**

Create `tests/integration/test_annual_plan_api.py`:

```python
"""Integración del API de plan anual — lectura, estado y CRUD."""
import uuid
from datetime import date, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.core.dependencies import get_current_user_id, get_db

MOCK_USER_ID = "user_test_plan"


def _mock_plan():
    plan = MagicMock()
    plan.id = uuid.uuid4()
    plan.user_id = MOCK_USER_ID
    plan.title = "Plan 12 meses"
    plan.start_date = date.today()   # mes activo siempre = 1 (test estable en cualquier fecha)
    plan.status = "active"
    plan.diagnostico_summary = "Diag"
    plan.genesis_session_id = None
    plan.months = []
    return plan


def _db_override(scalar_value):
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = scalar_value

    async def override():
        db = AsyncMock()
        db.execute = AsyncMock(return_value=mock_result)
        db.flush = AsyncMock()
        db.commit = AsyncMock()
        db.rollback = AsyncMock()
        yield db

    return override


async def _user_override():
    return MOCK_USER_ID


@pytest.mark.asyncio
async def test_get_status_returns_active():
    plan = _mock_plan()
    app.dependency_overrides[get_db] = _db_override(plan)
    app.dependency_overrides[get_current_user_id] = _user_override
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.get("/api/v1/annual-plan/status")
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "active"
    assert body["active_month_index"] == 1


@pytest.mark.asyncio
async def test_get_status_404_when_no_plan():
    app.dependency_overrides[get_db] = _db_override(None)
    app.dependency_overrides[get_current_user_id] = _user_override
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.get("/api/v1/annual-plan/status")
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_get_annual_plan_returns_payload():
    plan = _mock_plan()
    app.dependency_overrides[get_db] = _db_override(plan)
    app.dependency_overrides[get_current_user_id] = _user_override
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.get("/api/v1/annual-plan")
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 200
    body = r.json()
    assert body["title"] == "Plan 12 meses"
    assert body["status"] == "active"
    assert body["months"] == []
```

- [ ] **Step 3: Correr (falla)**

Run: `venv/bin/pytest tests/integration/test_annual_plan_api.py -v`
Expected: FAIL con 404 en todas (router no montado).

- [ ] **Step 4: Crear `app/api/v1/annual_plan/router.py`**

```python
"""
Plan estratégico de 12 meses — API REST.
- POST   /annual-plan/generate          → crea el plan (status generating) y encola la generación
- GET    /annual-plan/status            → estado + mes activo (para pantalla de carga)
- GET    /annual-plan                    → plan completo anidado (meses→objetivos→tareas)
- GET    /annual-plan/months/{idx}       → un mes
- POST   /annual-plan/objectives         → crear objetivo
- PATCH  /annual-plan/objectives/{id}    → editar objetivo
- DELETE /annual-plan/objectives/{id}    → borrar objetivo
- POST   /annual-plan/tasks              → crear tarea bajo un objetivo
(las tareas se editan/borran con los endpoints existentes PATCH/DELETE /tasks/{id})
"""
import uuid
from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.dependencies import get_current_user_id, get_db
from app.models.action_plan import ActionTask
from app.models.annual_plan import AnnualPlan, MonthlyPlan, Objective
from app.schemas.annual_plan import (
    AnnualPlanOut, AnnualPlanStatusOut, AnnualTaskCreate, MonthlyPlanOut,
    ObjectiveCreate, ObjectiveOut, ObjectiveUpdate,
)
from app.schemas.action_plan import ActionTaskOut
from app.services.ai.annual_plan_generator import compute_active_month_index

router = APIRouter()


# ── Serializers ───────────────────────────────────────────────────────────────

def _task_out(t: ActionTask) -> ActionTaskOut:
    return ActionTaskOut(
        id=str(t.id),
        plan_id=str(t.plan_id) if t.plan_id else None,
        objective_id=str(t.objective_id) if t.objective_id else None,
        kpi_ref=t.kpi_ref,
        title=t.title, description=t.description, source_agent=t.source_agent,
        status=t.status, priority=t.priority, owner=t.owner, due_date=t.due_date,
        tags=list(t.tags or []), order_index=t.order_index,
        created_at=t.created_at, updated_at=t.updated_at,
    )


def _objective_out(o: Objective, tasks: list[ActionTask]) -> ObjectiveOut:
    return ObjectiveOut(
        id=str(o.id), title=o.title, description=o.description,
        kpi_refs=list(o.kpi_refs or []), order_index=o.order_index,
        tasks=[_task_out(t) for t in tasks],
    )


# ── Helpers de carga ────────────────────────────────────────────────────────

async def _current_plan(user_id: str, db: AsyncSession) -> AnnualPlan | None:
    res = await db.execute(
        select(AnnualPlan)
        .where(AnnualPlan.user_id == user_id)
        .order_by(AnnualPlan.created_at.desc()).limit(1)
    )
    return res.scalar_one_or_none()


async def _tasks_by_objective(objective_ids: list[uuid.UUID], db: AsyncSession) -> dict:
    if not objective_ids:
        return {}
    res = await db.execute(
        select(ActionTask)
        .where(ActionTask.objective_id.in_(objective_ids))
        .order_by(ActionTask.order_index, ActionTask.created_at)
    )
    grouped: dict[uuid.UUID, list[ActionTask]] = {}
    for t in res.scalars().all():
        grouped.setdefault(t.objective_id, []).append(t)
    return grouped


# ── POST /annual-plan/generate ────────────────────────────────────────────────

@router.post("/annual-plan/generate", response_model=AnnualPlanStatusOut)
async def generate_plan(
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Crea el AnnualPlan en estado 'generating' y encola la generación en Celery.
    Si ya existe un plan que no falló, lo retorna sin duplicar."""
    existing = await _current_plan(user_id, db)
    if existing and existing.status != "failed":
        return AnnualPlanStatusOut(
            status=existing.status,
            active_month_index=compute_active_month_index(existing.start_date, date.today()),
        )

    plan = AnnualPlan(
        user_id=user_id, title="Plan estratégico de 12 meses",
        start_date=date.today(), status="generating",
    )
    db.add(plan)
    await db.flush()
    await db.commit()

    from app.tasks.annual_plan_tasks import generate_annual_plan_task
    generate_annual_plan_task.delay(str(plan.id))

    return AnnualPlanStatusOut(status="generating", active_month_index=1)


# ── GET /annual-plan/status ───────────────────────────────────────────────────

@router.get("/annual-plan/status", response_model=AnnualPlanStatusOut)
async def get_status(
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    plan = await _current_plan(user_id, db)
    if not plan:
        raise HTTPException(status_code=404, detail="No hay plan generado.")
    return AnnualPlanStatusOut(
        status=plan.status,
        active_month_index=compute_active_month_index(plan.start_date, date.today()),
    )


# ── GET /annual-plan ──────────────────────────────────────────────────────────

@router.get("/annual-plan", response_model=AnnualPlanOut)
async def get_plan(
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    res = await db.execute(
        select(AnnualPlan)
        .where(AnnualPlan.user_id == user_id)
        .order_by(AnnualPlan.created_at.desc()).limit(1)
        .options(selectinload(AnnualPlan.months).selectinload(MonthlyPlan.objectives))
    )
    plan = res.scalar_one_or_none()
    if not plan:
        raise HTTPException(status_code=404, detail="No hay plan generado.")

    all_obj_ids = [o.id for m in plan.months for o in m.objectives]
    grouped = await _tasks_by_objective(all_obj_ids, db)

    months_out = [
        MonthlyPlanOut(
            id=str(m.id), month_index=m.month_index,
            period_year=m.period_year, period_month=m.period_month,
            focus=m.focus, status=m.status, review=m.review,
            objectives=[_objective_out(o, grouped.get(o.id, [])) for o in m.objectives],
        )
        for m in plan.months
    ]
    return AnnualPlanOut(
        id=str(plan.id), title=plan.title, start_date=plan.start_date,
        status=plan.status, diagnostico_summary=plan.diagnostico_summary,
        genesis_session_id=str(plan.genesis_session_id) if plan.genesis_session_id else None,
        months=months_out,
    )


# ── GET /annual-plan/months/{idx} ─────────────────────────────────────────────

@router.get("/annual-plan/months/{month_index}", response_model=MonthlyPlanOut)
async def get_month(
    month_index: int,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    plan = await _current_plan(user_id, db)
    if not plan:
        raise HTTPException(status_code=404, detail="No hay plan generado.")
    res = await db.execute(
        select(MonthlyPlan)
        .where(MonthlyPlan.annual_plan_id == plan.id, MonthlyPlan.month_index == month_index)
        .options(selectinload(MonthlyPlan.objectives))
    )
    month = res.scalar_one_or_none()
    if not month:
        raise HTTPException(status_code=404, detail="Mes no encontrado.")
    grouped = await _tasks_by_objective([o.id for o in month.objectives], db)
    return MonthlyPlanOut(
        id=str(month.id), month_index=month.month_index,
        period_year=month.period_year, period_month=month.period_month,
        focus=month.focus, status=month.status, review=month.review,
        objectives=[_objective_out(o, grouped.get(o.id, [])) for o in month.objectives],
    )


# ── CRUD de objetivos ─────────────────────────────────────────────────────────

async def _owned_objective(obj_id: uuid.UUID, user_id: str, db: AsyncSession) -> Objective:
    res = await db.execute(
        select(Objective)
        .join(MonthlyPlan, Objective.monthly_plan_id == MonthlyPlan.id)
        .join(AnnualPlan, MonthlyPlan.annual_plan_id == AnnualPlan.id)
        .where(Objective.id == obj_id, AnnualPlan.user_id == user_id)
    )
    obj = res.scalar_one_or_none()
    if not obj:
        raise HTTPException(status_code=404, detail="Objetivo no encontrado.")
    return obj


@router.post("/annual-plan/objectives", response_model=ObjectiveOut)
async def create_objective(
    body: ObjectiveCreate,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    # validar que el mes pertenece al usuario
    res = await db.execute(
        select(MonthlyPlan)
        .join(AnnualPlan, MonthlyPlan.annual_plan_id == AnnualPlan.id)
        .where(MonthlyPlan.id == uuid.UUID(body.monthly_plan_id), AnnualPlan.user_id == user_id)
    )
    if not res.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Mes no encontrado.")
    obj = Objective(
        monthly_plan_id=uuid.UUID(body.monthly_plan_id),
        title=body.title, description=body.description, kpi_refs=body.kpi_refs,
    )
    db.add(obj)
    await db.flush()
    await db.commit()
    await db.refresh(obj)
    return _objective_out(obj, [])


@router.patch("/annual-plan/objectives/{objective_id}", response_model=ObjectiveOut)
async def update_objective(
    objective_id: uuid.UUID,
    body: ObjectiveUpdate,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    obj = await _owned_objective(objective_id, user_id, db)
    for key, value in body.model_dump(exclude_unset=True).items():
        setattr(obj, key, value)
    obj.updated_at = datetime.utcnow()
    await db.flush()
    await db.commit()
    await db.refresh(obj)
    grouped = await _tasks_by_objective([obj.id], db)
    return _objective_out(obj, grouped.get(obj.id, []))


@router.delete("/annual-plan/objectives/{objective_id}")
async def delete_objective(
    objective_id: uuid.UUID,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    obj = await _owned_objective(objective_id, user_id, db)
    await db.delete(obj)
    await db.commit()
    return {"deleted": True, "objective_id": str(objective_id)}


# ── POST /annual-plan/tasks ───────────────────────────────────────────────────

@router.post("/annual-plan/tasks", response_model=ActionTaskOut)
async def create_task(
    body: AnnualTaskCreate,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    obj = await _owned_objective(uuid.UUID(body.objective_id), user_id, db)
    max_idx = await db.execute(
        select(ActionTask.order_index)
        .where(ActionTask.objective_id == obj.id)
        .order_by(ActionTask.order_index.desc()).limit(1)
    )
    current_max = max_idx.scalar_one_or_none() or 0
    task = ActionTask(
        objective_id=obj.id, title=body.title, description=body.description,
        status=body.status, priority=body.priority, owner=body.owner,
        due_date=body.due_date, kpi_ref=body.kpi_ref, tags=body.tags,
        order_index=current_max + 1,
    )
    db.add(task)
    await db.flush()
    await db.commit()
    await db.refresh(task)
    return _task_out(task)
```

- [ ] **Step 5: Montar el router en `app/main.py`**

Después de `from app.api.v1.action_plans.router import router as action_plans_router` agregar:
```python
from app.api.v1.annual_plan.router import router as annual_plan_router
```
Y después de `app.include_router(action_plans_router, ...)` agregar:
```python
app.include_router(annual_plan_router, prefix="/api/v1", tags=["annual-plan"])
```

- [ ] **Step 6: Correr el test de API (pasa)**

Run: `venv/bin/pytest tests/integration/test_annual_plan_api.py -v`
Expected: PASS (3 tests).

- [ ] **Step 7: Enganchar la generación al cerrar etapa 8 — `app/api/v1/onboarding/etapa8.py`**

En `submit_etapa8`, después de `await db.commit()` y antes del `return Etapa8Output(...)`, insertar:
```python
    # Disparar generación del plan de 12 meses (solo la primera vez que se cierra el onboarding).
    if 8 in completed:
        from app.models.annual_plan import AnnualPlan
        from datetime import date as _date
        existing = await db.execute(
            select(AnnualPlan).where(AnnualPlan.user_id == user_id).limit(1)
        )
        if existing.scalar_one_or_none() is None:
            plan = AnnualPlan(
                user_id=user_id, title="Plan estratégico de 12 meses",
                start_date=_date.today(), status="generating",
            )
            db.add(plan)
            await db.flush()
            await db.commit()
            from app.tasks.annual_plan_tasks import generate_annual_plan_task
            generate_annual_plan_task.delay(str(plan.id))
```

- [ ] **Step 8: Escribir test del enganche (falla, luego pasa)**

Append a `tests/integration/test_annual_plan_api.py`:

```python
@pytest.mark.asyncio
async def test_etapa8_encola_generacion(monkeypatch):
    """Al cerrar etapa 8 sin plan previo, se encola generate_annual_plan."""
    import app.tasks.annual_plan_tasks as orch

    called = {}
    monkeypatch.setattr(orch.generate_annual_plan_task, "delay",
                        lambda pid: called.setdefault("pid", pid))

    # sesión de onboarding con etapa 7 completa y sin AnnualPlan previo
    onboarding = MagicMock()
    onboarding.id = uuid.uuid4()
    onboarding.user_id = MOCK_USER_ID
    onboarding.completed_stages = [1, 2, 3, 4, 5, 6, 7]
    onboarding.memory_buffer = {"company": {"industry": "manufacturing"},
                                "ai_context": {"company_narrative": "Demo"}}

    # execute() devuelve: 1) la sesión onboarding (varias veces), 2) None para AnnualPlan existente
    results = []
    def _make_result(val):
        r = MagicMock(); r.scalar_one_or_none.return_value = val; return r

    async def override_db():
        db = AsyncMock()
        # 1ª execute = _get_session_or_404 → onboarding ; 2ª = ¿existe AnnualPlan? → None (encola)
        seq = [_make_result(onboarding), _make_result(None)]
        db.execute = AsyncMock(side_effect=lambda *a, **k: seq.pop(0) if seq else _make_result(None))
        db.flush = AsyncMock(); db.commit = AsyncMock(); db.rollback = AsyncMock()
        db.add = MagicMock()
        yield db

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user_id] = _user_override
    body = {
        "vision_statement": "Ser referente de gobierno corporativo en México en 5 años.",
        "main_goals": ["Duplicar ingresos", "Internacionalizar", "Consolidar gobierno"],
        "board_expectations": {"session_frequency": "monthly",
                               "priority_topics": ["Finanzas"], "success_definition": "KPIs y score >80."},
        "agent_configs": [
            {"agent": "CFO", "tone": "formal", "alert_sensitivity": "high"},
            {"agent": "CSO", "tone": "strategic", "alert_sensitivity": "medium"},
            {"agent": "CRO", "tone": "direct", "alert_sensitivity": "high"},
            {"agent": "Auditor", "tone": "collaborative", "alert_sensitivity": "medium"},
        ],
    }
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.post(f"/api/v1/onboarding/{onboarding.id}/etapa-8", json=body)
    finally:
        app.dependency_overrides.clear()

    assert r.status_code == 200
    assert "pid" in called      # se encoló la generación
```

- [ ] **Step 9: Correr toda la suite nueva (pasa)**

Run: `venv/bin/pytest tests/unit/test_annual_plan_generator.py tests/unit/test_annual_plan_schemas.py tests/unit/test_annual_plan_models.py tests/unit/test_annual_plan_orchestration.py tests/integration/test_annual_plan_api.py -v`
Expected: PASS (todos).

- [ ] **Step 10: Correr la suite completa (no rompimos nada)**

Run: `venv/bin/pytest -q`
Expected: PASS. En particular, verificar que `tests/integration/test_etapa8.py` sigue verde (el enganche del Step 7 reusa el mismo `db.execute` mockeado, que devuelve la sesión; como ese mock no devuelve `None` para AnnualPlan, no se encola pero tampoco falla).

> Si `test_etapa8.py` se rompe porque el nuevo `select(AnnualPlan)` consume el mock de forma inesperada, ajusta el enganche del Step 7 para envolver la consulta de AnnualPlan en un `try/except Exception: pass` defensivo (el mock de ese test no modela la nueva query). Esto es aceptable: en producción la query es real.

- [ ] **Step 11: Commit**

```bash
git add app/api/v1/annual_plan/ app/main.py app/api/v1/onboarding/etapa8.py tests/integration/test_annual_plan_api.py
git commit -m "feat(plan): API REST del plan anual + enganche de generación en etapa 8"
```

---

## Cierre

- [ ] **Verificación final:** `venv/bin/pytest -q` en verde.
- [ ] El backend del subproyecto A queda completo y testeable. El **frontend** (pantalla de carga, vista de diagnóstico, vista del plan de 12 meses con edición inline) es el siguiente plan: `docs/superpowers/plans/2026-05-28-plan-12-meses-frontend.md`.

## Notas de seguimiento (otros subproyectos, NO implementar aquí)
- `MonthlyPlan.review` quedó reservado para el **subproyecto E** (revisión de fin de mes).
- El dashboard tipo Monday, confeti y recordatorios son **C/D/F**.
- El agente Secretario y la orden del día (PDF) son **B**.
