import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.models.board_theme import BoardTheme
from app.core.dependencies import get_current_user_id, get_db

MOCK_USER_ID = "user_test_pdf"


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
async def test_orden_del_dia_pdf():
    plan = MagicMock(); plan.id = uuid.uuid4(); plan.user_id = MOCK_USER_ID
    themes = [_theme("fin", "permanente", 1, 0)]
    month = MagicMock()
    month.id = uuid.uuid4(); month.month_index = 1
    month.period_year = 2026; month.period_month = 1
    month.covered_themes = ["fin"]; month.objectives = []
    onb = MagicMock(); onb.memory_buffer = {"company": {"name": "Acme"}}

    r1 = MagicMock(); r1.scalar_one_or_none.return_value = plan          # _current_plan
    r2 = MagicMock(); r2.scalars.return_value.all.return_value = themes  # themes
    r3 = MagicMock(); r3.scalar_one_or_none.return_value = month         # month
    r4 = MagicMock(); r4.scalar_one_or_none.return_value = onb           # onboarding
    db = AsyncMock(); db.execute = AsyncMock(side_effect=[r1, r2, r3, r4])

    app.dependency_overrides[get_db] = _db_override(db)
    app.dependency_overrides[get_current_user_id] = _user_override
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.get("/api/v1/annual-plan/months/1/orden-del-dia/pdf")
    finally:
        app.dependency_overrides.clear()

    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    assert r.content[:4] == b"%PDF"
    assert "attachment" in r.headers.get("content-disposition", "")
