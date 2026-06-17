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

    plan.horizon_years = 1

    monkeypatch.setattr(orch, "run_diagnostico", lambda buf: ({"CFO": {"summary": "ok"}}, {"CFO": {}}))
    monkeypatch.setattr(orch, "synthesize_diagnostico", lambda a: "Diag")
    monkeypatch.setattr(orch, "generate_milestones",
                        lambda *a, **k: {"items": []})
    monkeypatch.setattr(orch, "generate_quarter_plan",
                        lambda memory_buffer, kpi_labels, milestones, y, q: [
                            {"month_index": (y - 1) * 12 + (q - 1) * 3 + i,
                             "focus": "f", "objectives": []}
                            for i in range(1, 4)])

    await orch._run_generation(str(plan.id), db)

    assert plan.status == "active"
    assert plan.diagnostico_summary == "Diag"
    assert db.add_all.called or db.add.called
    assert db.commit.await_count >= 1

    # Idempotencia: se emitió un DELETE sobre monthly_plans antes de poblar.
    from sqlalchemy.sql.dml import Delete
    assert any(c.args and isinstance(c.args[0], Delete) for c in db.execute.call_args_list)


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


def test_run_diagnostico_applies_challenger(monkeypatch):
    from app.services.ai.agents import base

    monkeypatch.setattr(base, "run_agent_analysis",
                        lambda agent, *a, **k: {"summary": f"{agent} initial"})
    monkeypatch.setattr(base, "run_challenger_critique",
                        lambda *a, **k: {"weak_assumptions": ["supuesto débil"]})
    monkeypatch.setattr(base, "run_agent_revision",
                        lambda agent, initial, critique, *a, **k: {"summary": f"{agent} revised"})

    analyses, critiques = orch.run_diagnostico({"company": {}, "kpis": {}})

    # los 4 agentes, con análisis REVISADO (post-challenger) y crítica registrada
    assert set(analyses.keys()) == {"CFO", "CSO", "CRO", "Auditor"}
    assert analyses["CFO"]["summary"] == "CFO revised"
    assert critiques["CFO"] == {"weak_assumptions": ["supuesto débil"]}
