import uuid
from datetime import date
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.models.board_theme import BoardTheme
from app.core.dependencies import get_current_user_id, get_db

MOCK_USER_ID = "user_test_cobertura"


def _theme(key, type_, freq, order):
    return BoardTheme(key=key, label=key.title(), type=type_,
                      every_n_sessions=freq, active=True, order_index=order)


def _db_override(db):
    async def override():
        yield db
    return override


async def _user_override():
    return MOCK_USER_ID


@pytest.mark.asyncio
async def test_get_cobertura():
    plan = MagicMock(); plan.id = uuid.uuid4(); plan.user_id = MOCK_USER_ID
    plan.start_date = date.today()
    themes = [_theme("fin", "permanente", 1, 0), _theme("aud", "cobertura", 3, 1)]
    m1 = MagicMock(); m1.covered_themes = ["fin"]

    r1 = MagicMock(); r1.scalar_one_or_none.return_value = plan
    r2 = MagicMock(); r2.scalars.return_value.all.return_value = themes
    r3 = MagicMock(); r3.scalars.return_value.all.return_value = [m1]
    db = AsyncMock(); db.execute = AsyncMock(side_effect=[r1, r2, r3])

    app.dependency_overrides[get_db] = _db_override(db)
    app.dependency_overrides[get_current_user_id] = _user_override
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.get("/api/v1/annual-plan/cobertura")
    finally:
        app.dependency_overrides.clear()

    assert r.status_code == 200
    rows = {row["key"]: row for row in r.json()}
    assert rows["fin"]["estado"] == "en_tiempo"
    assert rows["aud"]["esperadas"] == 1
    assert rows["aud"]["estado"] == "riesgo"


@pytest.mark.asyncio
async def test_mark_coverage_adds_key():
    plan = MagicMock(); plan.id = uuid.uuid4(); plan.user_id = MOCK_USER_ID
    plan.start_date = date.today()
    month = MagicMock(); month.month_index = 1; month.covered_themes = []

    r1 = MagicMock(); r1.scalar_one_or_none.return_value = plan
    r2 = MagicMock(); r2.scalar_one_or_none.return_value = month
    db = AsyncMock(); db.execute = AsyncMock(side_effect=[r1, r2])
    db.flush = AsyncMock(); db.commit = AsyncMock()

    app.dependency_overrides[get_db] = _db_override(db)
    app.dependency_overrides[get_current_user_id] = _user_override
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.post("/api/v1/annual-plan/months/1/coverage",
                             json={"theme_key": "fin", "covered": True})
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 200
    assert "fin" in month.covered_themes


@pytest.mark.asyncio
async def test_mark_coverage_future_month_400():
    plan = MagicMock(); plan.id = uuid.uuid4(); plan.user_id = MOCK_USER_ID
    plan.start_date = date.today()
    r1 = MagicMock(); r1.scalar_one_or_none.return_value = plan
    db = AsyncMock(); db.execute = AsyncMock(side_effect=[r1])
    app.dependency_overrides[get_db] = _db_override(db)
    app.dependency_overrides[get_current_user_id] = _user_override
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.post("/api/v1/annual-plan/months/6/coverage",
                             json={"theme_key": "fin", "covered": True})
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 400
