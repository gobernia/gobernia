"""Integración del tablero operativo (tipo Monday) del plan anual.

- GET   /annual-plan/board          → todas las tareas agrupadas por mes
- PATCH /tasks/{id}/estado          → cambia el estatus SIN candado de evidencia
"""
import uuid
from datetime import date, datetime, timezone

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.models.action_plan import ActionTask
from app.models.annual_plan import AnnualPlan, MonthlyPlan, Objective
from app.core.dependencies import get_current_user_id, get_db

MOCK_USER_ID = "user_test_board"
NOW = datetime(2026, 3, 1, tzinfo=timezone.utc)


def _db_override(db):
    async def override():
        yield db
    return override


async def _user_override():
    return MOCK_USER_ID


def _task(objective_id, *, title="Tarea", owner=None, status="pendiente",
          priority="media", due_date=None, order_index=0):
    t = ActionTask(id=uuid.uuid4(), plan_id=None, objective_id=objective_id,
                   title=title, status=status, priority=priority,
                   owner=owner, due_date=due_date, order_index=order_index)
    t.created_at = NOW; t.updated_at = NOW
    t.kpi_ref = None; t.description = None; t.source_agent = None; t.tags = None
    return t


# ── GET /annual-plan/board ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_board_groups_by_month():
    # start_date = hoy → mes activo = 1 (test estable en cualquier fecha)
    plan = AnnualPlan(id=uuid.uuid4(), user_id=MOCK_USER_ID, title="P",
                      start_date=date.today(), status="active")
    plan.horizon_years = 1

    obj1 = Objective(id=uuid.uuid4(), monthly_plan_id=uuid.uuid4(),
                     title="Ordenar la operación", order_index=0)
    obj2 = Objective(id=uuid.uuid4(), monthly_plan_id=uuid.uuid4(),
                     title="Crecer", order_index=0)

    month1 = MonthlyPlan(id=uuid.uuid4(), annual_plan_id=plan.id, month_index=1,
                         period_year=2026, period_month=3, status="active")
    month1.objectives = [obj1]
    month2 = MonthlyPlan(id=uuid.uuid4(), annual_plan_id=plan.id, month_index=2,
                         period_year=2026, period_month=4, status="locked")
    month2.objectives = [obj2]

    t1 = _task(obj1.id, title="Cerrar caja", owner="Dirección General",
               status="en_progreso", priority="alta", due_date=date(2026, 3, 15),
               order_index=0)
    t2 = _task(obj2.id, title="Abrir sucursal", owner="Ventas",
               status="pendiente", priority="baja", order_index=0)

    from unittest.mock import AsyncMock, MagicMock
    r1 = MagicMock(); r1.scalar_one_or_none.return_value = plan
    r2 = MagicMock(); r2.scalars.return_value.all.return_value = [month1, month2]
    r3 = MagicMock(); r3.scalars.return_value.all.return_value = [t1, t2]
    db = AsyncMock(); db.execute = AsyncMock(side_effect=[r1, r2, r3])

    app.dependency_overrides[get_db] = _db_override(db)
    app.dependency_overrides[get_current_user_id] = _user_override
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.get("/api/v1/annual-plan/board")
    finally:
        app.dependency_overrides.clear()

    assert r.status_code == 200
    body = r.json()
    meses = body["meses"]
    assert [m["month_index"] for m in meses] == [1, 2]

    m1 = meses[0]
    assert m1["label"] == "Marzo 2026"
    assert m1["es_mes_actual"] is True
    assert len(m1["tareas"]) == 1
    tarea = m1["tareas"][0]
    assert tarea["title"] == "Cerrar caja"
    assert tarea["owner"] == "Dirección General"
    assert tarea["status"] == "en_progreso"
    assert tarea["priority"] == "alta"
    assert tarea["due_date"] == "2026-03-15"
    assert tarea["objetivo"] == "Ordenar la operación"
    assert tarea["viene_de"] is None
    # Mes actual (=1) sin meses anteriores → sin arrastre.
    assert m1["arrastradas"] == []

    m2 = meses[1]
    assert m2["label"] == "Abril 2026"
    assert m2["es_mes_actual"] is False
    assert m2["tareas"][0]["objetivo"] == "Crecer"
    assert m2["arrastradas"] == []


def _start_n_months_ago(n: int) -> date:
    """start_date tal que compute_active_month_index(...) == n+1 hoy (test estable)."""
    today = date.today()
    month = today.month - n
    year = today.year
    while month <= 0:
        month += 12
        year -= 1
    return date(year, month, 1)


@pytest.mark.asyncio
async def test_board_arrastra_incompletas_al_mes_actual():
    # Mes activo = 3 (arranca 2 meses atrás). Meses 1 y 2 tienen tareas incompletas.
    plan = AnnualPlan(id=uuid.uuid4(), user_id=MOCK_USER_ID, title="P",
                      start_date=_start_n_months_ago(2), status="active")
    plan.horizon_years = 1

    obj1 = Objective(id=uuid.uuid4(), monthly_plan_id=uuid.uuid4(), title="Enero obj", order_index=0)
    obj2 = Objective(id=uuid.uuid4(), monthly_plan_id=uuid.uuid4(), title="Febrero obj", order_index=0)
    obj3 = Objective(id=uuid.uuid4(), monthly_plan_id=uuid.uuid4(), title="Marzo obj", order_index=0)

    month1 = MonthlyPlan(id=uuid.uuid4(), annual_plan_id=plan.id, month_index=1,
                         period_year=2026, period_month=1, status="done")
    month1.objectives = [obj1]
    month2 = MonthlyPlan(id=uuid.uuid4(), annual_plan_id=plan.id, month_index=2,
                         period_year=2026, period_month=2, status="done")
    month2.objectives = [obj2]
    month3 = MonthlyPlan(id=uuid.uuid4(), annual_plan_id=plan.id, month_index=3,
                         period_year=2026, period_month=3, status="active")
    month3.objectives = [obj3]

    # Enero: una completada (NO se arrastra) y una pendiente (SÍ se arrastra).
    t_done = _task(obj1.id, title="Enero hecha", status="completada", order_index=0)
    t_ene = _task(obj1.id, title="Enero pendiente", status="pendiente", order_index=1)
    # Febrero: una en progreso (SÍ se arrastra).
    t_feb = _task(obj2.id, title="Febrero en curso", status="en_progreso", order_index=0)
    # Marzo (mes actual): tarea propia.
    t_mar = _task(obj3.id, title="Marzo propia", status="pendiente", order_index=0)

    from unittest.mock import AsyncMock, MagicMock
    r1 = MagicMock(); r1.scalar_one_or_none.return_value = plan
    r2 = MagicMock(); r2.scalars.return_value.all.return_value = [month1, month2, month3]
    r3 = MagicMock(); r3.scalars.return_value.all.return_value = [t_done, t_ene, t_feb, t_mar]
    db = AsyncMock(); db.execute = AsyncMock(side_effect=[r1, r2, r3])

    app.dependency_overrides[get_db] = _db_override(db)
    app.dependency_overrides[get_current_user_id] = _user_override
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.get("/api/v1/annual-plan/board")
    finally:
        app.dependency_overrides.clear()

    assert r.status_code == 200
    meses = r.json()["meses"]
    m1, m2, m3 = meses

    # Los meses pasados NO se mutan: sus tareas quedan en `tareas` con su status real, sin arrastre.
    assert [t["title"] for t in m1["tareas"]] == ["Enero hecha", "Enero pendiente"]
    assert all(t["viene_de"] is None for t in m1["tareas"])
    assert m1["arrastradas"] == []
    assert [t["title"] for t in m2["tareas"]] == ["Febrero en curso"]
    assert m2["arrastradas"] == []

    # El mes actual conserva su tarea propia en `tareas`...
    assert [t["title"] for t in m3["tareas"]] == ["Marzo propia"]
    assert m3["tareas"][0]["viene_de"] is None
    # ...y reúne las incompletas de meses anteriores en `arrastradas`, con su mes de origen.
    arr = m3["arrastradas"]
    assert [t["title"] for t in arr] == ["Enero pendiente", "Febrero en curso"]
    assert arr[0]["viene_de"] == "Enero 2026"
    assert arr[1]["viene_de"] == "Febrero 2026"
    # La completada de Enero NO se arrastra.
    assert all(t["title"] != "Enero hecha" for t in arr)


@pytest.mark.asyncio
async def test_board_empty_when_no_plan():
    from unittest.mock import AsyncMock, MagicMock
    r1 = MagicMock(); r1.scalar_one_or_none.return_value = None
    db = AsyncMock(); db.execute = AsyncMock(side_effect=[r1])

    app.dependency_overrides[get_db] = _db_override(db)
    app.dependency_overrides[get_current_user_id] = _user_override
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.get("/api/v1/annual-plan/board")
    finally:
        app.dependency_overrides.clear()

    assert r.status_code == 200
    assert r.json() == {"meses": []}


# ── PATCH /tasks/{id}/estado ──────────────────────────────────────────────────

def _estado_db(task, *, owned=True):
    """Mock del flujo _get_user_task_or_404: r1=carga tarea, r2=chequeo de propiedad."""
    from unittest.mock import AsyncMock, MagicMock
    r1 = MagicMock(); r1.scalar_one_or_none.return_value = task
    r2 = MagicMock(); r2.scalar_one_or_none.return_value = (uuid.uuid4() if owned else None)
    db = AsyncMock(); db.execute = AsyncMock(side_effect=[r1, r2])
    db.flush = AsyncMock(); db.commit = AsyncMock(); db.refresh = AsyncMock()
    return db


@pytest.mark.parametrize("nuevo_estado", ["pendiente", "en_progreso", "completada"])
@pytest.mark.asyncio
async def test_estado_cambia_sin_evidencia(nuevo_estado):
    # required_doc puesto y CERO evidencias: la vía del tablero NO exige nada.
    task = _task(uuid.uuid4(), status="pendiente")
    task.required_doc = "Acta firmada"
    db = _estado_db(task)

    app.dependency_overrides[get_db] = _db_override(db)
    app.dependency_overrides[get_current_user_id] = _user_override
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.patch(f"/api/v1/tasks/{task.id}/estado", json={"status": nuevo_estado})
    finally:
        app.dependency_overrides.clear()

    assert r.status_code == 200
    assert r.json()["status"] == nuevo_estado
    assert task.status == nuevo_estado


@pytest.mark.asyncio
async def test_estado_invalido_400():
    task = _task(uuid.uuid4())
    db = _estado_db(task)

    app.dependency_overrides[get_db] = _db_override(db)
    app.dependency_overrides[get_current_user_id] = _user_override
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.patch(f"/api/v1/tasks/{task.id}/estado", json={"status": "archivada"})
    finally:
        app.dependency_overrides.clear()

    assert r.status_code == 400


@pytest.mark.asyncio
async def test_estado_tarea_de_otro_usuario_404():
    task = _task(uuid.uuid4())
    db = _estado_db(task, owned=False)

    app.dependency_overrides[get_db] = _db_override(db)
    app.dependency_overrides[get_current_user_id] = _user_override
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.patch(f"/api/v1/tasks/{task.id}/estado", json={"status": "completada"})
    finally:
        app.dependency_overrides.clear()

    assert r.status_code == 404
