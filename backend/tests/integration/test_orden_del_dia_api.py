import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.core.dependencies import get_current_user_id, get_db

MOCK_USER_ID = "user_test_orden"


def _theme(key, type_, freq, order, active=True):
    t = MagicMock()
    t.id = uuid.uuid4(); t.key = key; t.label = key.replace("_", " ").title()
    t.type = type_; t.every_n_sessions = freq; t.active = active; t.order_index = order
    return t


def _db_override(db):
    async def override():
        yield db
    return override


async def _user_override():
    return MOCK_USER_ID


@pytest.mark.asyncio
async def test_orden_del_dia_mes_1():
    plan = MagicMock(); plan.id = uuid.uuid4(); plan.user_id = MOCK_USER_ID
    themes = [
        _theme("resultados_financieros", "permanente", 1, 1),
        _theme("auditoria", "cobertura", 3, 7),              # mes 1 -> programado
        _theme("cumplimiento_normativo", "cobertura", 3, 8), # mes 1 -> NO (2,5,8,11)
    ]
    month = MagicMock()
    month.id = uuid.uuid4(); month.month_index = 1
    month.period_year = 2026; month.period_month = 1; month.objectives = []

    r1 = MagicMock(); r1.scalar_one_or_none.return_value = plan          # _current_plan
    r2 = MagicMock(); r2.scalars.return_value.all.return_value = themes  # themes query
    r3 = MagicMock(); r3.scalar_one_or_none.return_value = month         # month query
    db = AsyncMock(); db.execute = AsyncMock(side_effect=[r1, r2, r3])

    app.dependency_overrides[get_db] = _db_override(db)
    app.dependency_overrides[get_current_user_id] = _user_override
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.get("/api/v1/annual-plan/months/1/orden-del-dia")
    finally:
        app.dependency_overrides.clear()

    assert r.status_code == 200
    body = r.json()
    assert body["month_index"] == 1
    assert {t["key"] for t in body["permanent_themes"]} == {"resultados_financieros"}
    assert {t["key"] for t in body["coverage_themes"]} == {"auditoria"}


@pytest.mark.asyncio
async def test_orden_del_dia_404_sin_plan():
    r1 = MagicMock(); r1.scalar_one_or_none.return_value = None
    db = AsyncMock(); db.execute = AsyncMock(side_effect=[r1])
    app.dependency_overrides[get_db] = _db_override(db)
    app.dependency_overrides[get_current_user_id] = _user_override
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.get("/api/v1/annual-plan/months/1/orden-del-dia")
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 404
