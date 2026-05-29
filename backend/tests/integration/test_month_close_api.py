"""Integración de cierre de mes y aplicar propuesta."""
import uuid
from datetime import date
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.core.dependencies import get_current_user_id, get_db
import app.api.v1.annual_plan.router as plan_router

MOCK_USER_ID = "user_test_close"


async def _user_override():
    return MOCK_USER_ID


@pytest.mark.asyncio
async def test_close_month_not_active_409(monkeypatch):
    month = MagicMock()
    month.status = "locked"
    monkeypatch.setattr(plan_router, "_load_owned_month",
                        AsyncMock(return_value=month))

    async def override_db():
        db = AsyncMock(); db.commit = AsyncMock(); yield db
    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user_id] = _user_override
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.post("/api/v1/annual-plan/months/3/close", json={"kpis": {}})
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 409


@pytest.mark.asyncio
async def test_close_month_runs_review(monkeypatch):
    active_month = MagicMock()
    active_month.status = "active"
    monkeypatch.setattr(plan_router, "_load_owned_month",
                        AsyncMock(return_value=active_month))
    monkeypatch.setattr(
        plan_router, "_run_close",
        AsyncMock(return_value={"month_index": 1, "active_month_index": 2,
                                "grade": "bien"}))

    async def override_db():
        db = AsyncMock(); yield db
    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user_id] = _user_override
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.post("/api/v1/annual-plan/months/1/close", json={"kpis": {"Razón corriente": 1.2}})
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 200
    assert r.json()["grade"] == "bien"
