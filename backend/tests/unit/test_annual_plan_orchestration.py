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

    onboarding = MagicMock()
    onboarding.memory_buffer = {"company": {"name": "Demo"}, "kpis": {}}

    db = AsyncMock()
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
