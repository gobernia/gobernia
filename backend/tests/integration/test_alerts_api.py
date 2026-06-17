import uuid
from datetime import date
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.models.board_theme import BoardTheme
from app.core.dependencies import get_current_user_id, get_db

MOCK_USER_ID = "user_test_alertas"


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
async def test_get_alertas():
    plan = MagicMock(); plan.id = uuid.uuid4(); plan.user_id = MOCK_USER_ID
    plan.start_date = date(2020, 1, 1); plan.horizon_years = 1  # mes activo = 12 (cap) → hay meses ya pasados
    month = MagicMock()
    month.id = uuid.uuid4(); month.month_index = 1
    month.objectives = []; month.covered_themes = []
    month.status = "active"; month.review = None
    themes = [_theme("fin", "permanente", 1, 0)]  # activo=12, no cubierto -> esperadas 11, deficit 11 perm -> critico (alerta)

    r1 = MagicMock(); r1.scalar_one_or_none.return_value = plan          # _current_plan
    r2 = MagicMock(); r2.scalars.return_value.all.return_value = [month] # months
    r3 = MagicMock(); r3.scalars.return_value.all.return_value = themes  # themes (sin objetivos -> sin query de tasks)
    db = AsyncMock(); db.execute = AsyncMock(side_effect=[r1, r2, r3])

    app.dependency_overrides[get_db] = _db_override(db)
    app.dependency_overrides[get_current_user_id] = _user_override
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.get("/api/v1/annual-plan/alertas")
    finally:
        app.dependency_overrides.clear()

    assert r.status_code == 200
    body = r.json()
    assert isinstance(body, list)
    assert any(x["category"] == "cobertura" for x in body)
