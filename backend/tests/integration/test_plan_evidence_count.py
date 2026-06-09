import uuid
from datetime import date, datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.models.action_plan import ActionTask
from app.models.annual_plan import AnnualPlan, MonthlyPlan, Objective
from app.api.v1.annual_plan.router import _task_out, _objective_out
from app.core.dependencies import get_current_user_id, get_db

MOCK_USER_ID = "user_test_evcount"
NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _task(objective_id=None):
    t = ActionTask(id=uuid.uuid4(), plan_id=None, objective_id=objective_id,
                   title="A", status="pendiente", priority="media", order_index=0)
    t.created_at = NOW; t.updated_at = NOW
    t.kpi_ref = None; t.description = None; t.source_agent = None
    t.owner = None; t.due_date = None; t.tags = None
    return t


def test_task_out_threads_evidence_count():
    t = _task()
    assert _task_out(t, 3).evidence_count == 3


def test_task_out_defaults_zero():
    t = _task()
    assert _task_out(t).evidence_count == 0


def test_objective_out_threads_counts():
    obj = Objective(id=uuid.uuid4(), monthly_plan_id=uuid.uuid4(), title="O", order_index=0)
    obj.kpi_refs = None
    t = _task(objective_id=obj.id)
    out = _objective_out(obj, [t], {t.id: 5})
    assert out.tasks[0].evidence_count == 5


def _db_override(db):
    async def override():
        yield db
    return override


async def _user_override():
    return MOCK_USER_ID


@pytest.mark.asyncio
async def test_get_plan_includes_evidence_count():
    plan = AnnualPlan(id=uuid.uuid4(), user_id=MOCK_USER_ID, title="P",
                      start_date=date.today(), status="active")
    plan.diagnostico_summary = None; plan.genesis_session_id = None
    month = MonthlyPlan(id=uuid.uuid4(), annual_plan_id=plan.id, month_index=1,
                        period_year=2026, period_month=1, status="active")
    month.focus = None; month.review = None
    obj = Objective(id=uuid.uuid4(), monthly_plan_id=month.id, title="O", order_index=0)
    obj.kpi_refs = None
    month.objectives = [obj]
    plan.months = [month]
    task = _task(objective_id=obj.id)

    r1 = MagicMock(); r1.scalar_one_or_none.return_value = plan
    r2 = MagicMock(); r2.scalars.return_value.all.return_value = [task]
    r3 = MagicMock(); r3.all.return_value = [(task.id, 2)]
    db = AsyncMock(); db.execute = AsyncMock(side_effect=[r1, r2, r3])

    app.dependency_overrides[get_db] = _db_override(db)
    app.dependency_overrides[get_current_user_id] = _user_override
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.get("/api/v1/annual-plan")
    finally:
        app.dependency_overrides.clear()

    assert r.status_code == 200
    body = r.json()
    assert body["months"][0]["objectives"][0]["tasks"][0]["evidence_count"] == 2
