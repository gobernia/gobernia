import pytest
from unittest.mock import AsyncMock, MagicMock
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.core.dependencies import get_current_user_id, get_db


def _user():
    return "user-123"


def _db_override(db):
    async def _dep():
        yield db
    return _dep


@pytest.mark.asyncio
async def test_get_roadmap_sin_plan_da_404():
    db = AsyncMock()
    res = MagicMock(); res.scalar_one_or_none.return_value = None
    db.execute = AsyncMock(return_value=res)
    app.dependency_overrides[get_db] = _db_override(db)
    app.dependency_overrides[get_current_user_id] = _user
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.get("/api/v1/annual-plan/roadmap")
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_patch_roadmap_guarda_y_devuelve():
    plan = MagicMock(); plan.roadmap = {}
    res = MagicMock(); res.scalar_one_or_none.return_value = plan
    db = AsyncMock(); db.execute = AsyncMock(return_value=res); db.commit = AsyncMock()
    app.dependency_overrides[get_db] = _db_override(db)
    app.dependency_overrides[get_current_user_id] = _user
    body = {"vision": "Nueva visión", "pilares": []}
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.patch("/api/v1/annual-plan/roadmap", json=body)
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 200
    assert r.json()["vision"] == "Nueva visión"
    assert plan.roadmap["vision"] == "Nueva visión"
