"""
Tests para la orquestación trimestre-primero (N×12 meses + hitos).
Mockea todas las llamadas a IA y a la DB; no toca red ni Postgres.
"""
import uuid
from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch, call

import pytest

import app.tasks.annual_plan_tasks as orch
from app.models.action_plan import ActionTask
from app.models.annual_plan import MonthlyPlan


def _make_quarter_result(year: int, quarter: int) -> list[dict]:
    """3 month-dicts con month_index globales, objectives vacíos."""
    base = (year - 1) * 12 + (quarter - 1) * 3
    return [{"month_index": base + i, "focus": None, "objectives": []} for i in range(1, 4)]


@pytest.mark.asyncio
async def test_run_generation_3anios_1_year(monkeypatch):
    """horizon_years=1 → 12 MonthlyPlan añadidos, milestones seteados, status active."""
    plan = MagicMock()
    plan.id = uuid.uuid4()
    plan.user_id = "u1"
    plan.start_date = date(2026, 1, 1)
    plan.horizon_years = 1
    plan.status = "generating"
    plan.genesis_session_id = None

    onboarding = MagicMock()
    onboarding.id = uuid.uuid4()
    onboarding.memory_buffer = {"company": {"name": "ACME"}, "kpis": {}}

    # db.get devuelve el plan (primera llamada = carga inicial)
    db = AsyncMock()
    db.get = AsyncMock(return_value=plan)

    # db.execute: primera llamada = onboarding query, segunda = delete MonthlyPlan
    onb_result = MagicMock()
    onb_result.scalar_one_or_none.return_value = onboarding
    db.execute = AsyncMock(return_value=onb_result)

    db.add = MagicMock()
    db.flush = AsyncMock()
    db.commit = AsyncMock()

    fake_milestones = {"items": [
        {"type": "anual", "year": 1, "period": 1, "title": "Meta año 1",
         "target": "crecer 20%", "kpi_ref": None}
    ]}

    monkeypatch.setattr(orch, "run_diagnostico",
                        lambda buf: ({"CFO": {"summary": "ok"}}, {"CFO": {}}))
    monkeypatch.setattr(orch, "synthesize_diagnostico", lambda a: "diag")
    monkeypatch.setattr(orch, "generate_milestones",
                        lambda *a, **k: fake_milestones)
    monkeypatch.setattr(orch, "generate_quarter_plan",
                        lambda memory_buffer, kpi_labels, milestones, y, q:
                        _make_quarter_result(y, q))

    await orch._run_generation(str(plan.id), db)

    # 12 MonthlyPlan creados (horizon_years=1 → 4 quarters × 3 months)
    added_monthly_plans = [
        c.args[0] for c in db.add.call_args_list
        if isinstance(c.args[0], MonthlyPlan)
    ]
    assert len(added_monthly_plans) == 12, (
        f"Esperados 12 MonthlyPlan, se añadieron {len(added_monthly_plans)}"
    )

    # milestones seteados en el plan
    assert plan.milestones == fake_milestones

    # status final
    assert plan.status == "active"

    # commit llamado al menos una vez
    assert db.commit.await_count >= 1


@pytest.mark.asyncio
async def test_run_generation_3anios_marca_failed_en_error(monkeypatch):
    """Si generate_milestones lanza, el plan queda 'failed'."""
    plan = MagicMock()
    plan.id = uuid.uuid4()
    plan.user_id = "u1"
    plan.start_date = date(2026, 1, 1)
    plan.horizon_years = 1
    plan.status = "generating"
    plan.genesis_session_id = None

    onboarding = MagicMock()
    onboarding.id = uuid.uuid4()
    onboarding.memory_buffer = {}

    db = AsyncMock()
    db.get = AsyncMock(return_value=plan)
    onb_result = MagicMock()
    onb_result.scalar_one_or_none.return_value = onboarding
    db.execute = AsyncMock(return_value=onb_result)
    db.add = MagicMock()
    db.flush = AsyncMock()
    db.rollback = AsyncMock()
    db.commit = AsyncMock()

    monkeypatch.setattr(orch, "run_diagnostico",
                        lambda buf: ({"CFO": {"summary": "ok"}}, {}))
    monkeypatch.setattr(orch, "synthesize_diagnostico", lambda a: "diag")
    monkeypatch.setattr(orch, "generate_milestones",
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))

    with pytest.raises(RuntimeError, match="boom"):
        await orch._run_generation(str(plan.id), db)

    assert plan.status == "failed"


@pytest.mark.asyncio
async def test_run_generation_3anios_3_years(monkeypatch):
    """horizon_years=3 → 36 MonthlyPlan añadidos."""
    plan = MagicMock()
    plan.id = uuid.uuid4()
    plan.user_id = "u1"
    plan.start_date = date(2026, 1, 1)
    plan.horizon_years = 3
    plan.status = "generating"
    plan.genesis_session_id = None

    onboarding = MagicMock()
    onboarding.id = uuid.uuid4()
    onboarding.memory_buffer = {}

    db = AsyncMock()
    db.get = AsyncMock(return_value=plan)
    onb_result = MagicMock()
    onb_result.scalar_one_or_none.return_value = onboarding
    db.execute = AsyncMock(return_value=onb_result)
    db.add = MagicMock()
    db.flush = AsyncMock()
    db.commit = AsyncMock()

    fake_milestones = {"items": []}

    monkeypatch.setattr(orch, "run_diagnostico", lambda buf: ({}, {}))
    monkeypatch.setattr(orch, "synthesize_diagnostico", lambda a: "")
    monkeypatch.setattr(orch, "generate_milestones", lambda *a, **k: fake_milestones)
    monkeypatch.setattr(orch, "generate_quarter_plan",
                        lambda memory_buffer, kpi_labels, milestones, y, q:
                        _make_quarter_result(y, q))

    await orch._run_generation(str(plan.id), db)

    added_monthly_plans = [
        c.args[0] for c in db.add.call_args_list
        if isinstance(c.args[0], MonthlyPlan)
    ]
    assert len(added_monthly_plans) == 36, (
        f"Esperados 36 MonthlyPlan, se añadieron {len(added_monthly_plans)}"
    )
    assert plan.status == "active"


@pytest.mark.asyncio
async def test_run_generation_con_tareas_no_lanza_user_id(monkeypatch):
    """
    Regresión: ActionTask no tiene columna user_id.
    Si generate_quarter_plan devuelve un objetivo CON tareas, el constructor
    de ActionTask debe llamarse sin user_id — este test lo forzaría a fallar
    si la línea 'user_id=plan.user_id' volviera a aparecer.
    """
    from app.services.ai.annual_plan_generator import quarter_month_indices

    plan = MagicMock()
    plan.id = uuid.uuid4()
    plan.user_id = "u1"
    plan.start_date = date(2026, 1, 1)
    plan.horizon_years = 1
    plan.status = "generating"
    plan.genesis_session_id = None

    onboarding = MagicMock()
    onboarding.id = uuid.uuid4()
    onboarding.memory_buffer = {"company": {"name": "ACME"}, "kpis": {}}

    db = AsyncMock()
    db.get = AsyncMock(return_value=plan)
    onb_result = MagicMock()
    onb_result.scalar_one_or_none.return_value = onboarding
    db.execute = AsyncMock(return_value=onb_result)
    db.add = MagicMock()
    db.flush = AsyncMock()
    db.commit = AsyncMock()

    fake_milestones = {"items": []}

    def _fake_quarter(memory_buffer, kpi_labels, milestones, year, quarter):
        idxs = quarter_month_indices(year, quarter)
        return [
            {"month_index": idxs[0], "focus": "F", "objectives": [
                {"title": "Obj", "description": None, "kpi_refs": ["Margen"], "tasks": [
                    {"title": "Subir margen", "description": None, "owner": "CFO",
                     "priority": "alta", "kpi_ref": "Margen",
                     "required_doc": "estado de resultados",
                     "tags": [], "due_day": 15}
                ]}
            ]},
            {"month_index": idxs[1], "focus": None, "objectives": []},
            {"month_index": idxs[2], "focus": None, "objectives": []},
        ]

    monkeypatch.setattr(orch, "run_diagnostico",
                        lambda buf: ({"CFO": {"summary": "ok"}}, {"CFO": {}}))
    monkeypatch.setattr(orch, "synthesize_diagnostico", lambda a: "diag")
    monkeypatch.setattr(orch, "generate_milestones",
                        lambda *a, **k: fake_milestones)
    monkeypatch.setattr(orch, "generate_quarter_plan", _fake_quarter)

    # No debe lanzar TypeError por user_id
    await orch._run_generation(str(plan.id), db)

    # Al menos una ActionTask fue añadida a la db
    added_action_tasks = [
        c.args[0] for c in db.add.call_args_list
        if isinstance(c.args[0], ActionTask)
    ]
    assert len(added_action_tasks) >= 1, (
        "Se esperaba al menos una ActionTask añadida; "
        f"calls: {[type(c.args[0]).__name__ for c in db.add.call_args_list]}"
    )
    assert plan.status == "active"
