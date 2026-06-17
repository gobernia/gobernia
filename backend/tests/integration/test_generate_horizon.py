import uuid
from datetime import date
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.core.dependencies import get_current_user_id, get_db
from app.models.annual_plan import AnnualPlan

MOCK_USER_ID = "user_test_horizon"


def _onboarding_completo():
    onb = MagicMock()
    onb.completed_stages = [1, 2, 3, 4, 5, 6, 7, 8]
    onb.memory_buffer = {
        "company": {"name": "ACME"},
        "kpis": {"finance": [{"label": "Margen", "current_value": 12.0, "unknown": False}]},
    }
    return onb


def _db_override(db):
    async def override():
        yield db
    return override


async def _user_override():
    return MOCK_USER_ID


@pytest.mark.asyncio
async def test_generate_acepta_horizon_3(monkeypatch):
    """POST /annual-plan/generate con horizon_years=3 crea un AnnualPlan con horizon_years==3."""
    async def fake_seed(db, plan_id):
        return 13

    monkeypatch.setattr("app.api.v1.annual_plan.router.seed_default_themes", fake_seed)
    monkeypatch.setattr("app.tasks.annual_plan_tasks.generate_annual_plan_task.delay",
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("no celery")))

    onb = _onboarding_completo()
    onb_result = MagicMock()
    onb_result.scalar_one_or_none.return_value = onb

    plan_result = MagicMock()
    plan_result.scalar_one_or_none.return_value = None  # no hay plan previo

    db = AsyncMock()
    db.execute = AsyncMock(side_effect=[onb_result, plan_result])
    db.add = MagicMock()
    db.flush = AsyncMock()
    db.commit = AsyncMock()

    app.dependency_overrides[get_db] = _db_override(db)
    app.dependency_overrides[get_current_user_id] = _user_override
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.post("/api/v1/annual-plan/generate", json={"horizon_years": 3})
    finally:
        app.dependency_overrides.clear()

    # El endpoint devuelve 503 (Celery no disponible) pero el plan ya fue creado con db.add
    assert r.status_code in (200, 503)

    # Verificar que el AnnualPlan fue construido con horizon_years=3
    added_plan = next(
        (call.args[0] for call in db.add.call_args_list if isinstance(call.args[0], AnnualPlan)),
        None,
    )
    assert added_plan is not None, "db.add debería haberse llamado con un AnnualPlan"
    assert added_plan.horizon_years == 3
    assert "3 año(s)" in added_plan.title


@pytest.mark.asyncio
async def test_generate_rechaza_horizon_invalido():
    """POST /annual-plan/generate con horizon_years=5 debe retornar 422."""
    app.dependency_overrides[get_current_user_id] = _user_override
    # No necesitamos db override porque la validación pydantic ocurre antes
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.post("/api/v1/annual-plan/generate", json={"horizon_years": 5})
    finally:
        app.dependency_overrides.clear()

    assert r.status_code == 422
