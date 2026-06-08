import uuid
from datetime import date
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.core.dependencies import get_current_user_id, get_db

MOCK_USER_ID = "user_test_themes"


def _plan():
    p = MagicMock()
    p.id = uuid.uuid4()
    p.user_id = MOCK_USER_ID
    p.status = "active"
    p.start_date = date.today()
    return p


def _theme(label="Finanzas", type_="permanente", freq=1):
    t = MagicMock()
    t.id = uuid.uuid4()
    t.key = "finanzas"
    t.label = label
    t.type = type_
    t.every_n_sessions = freq
    t.active = True
    t.is_default = True
    t.order_index = 0
    return t


def _db_for_list(plan, themes):
    """_current_plan usa scalar_one_or_none; list usa scalars().all()."""
    result = MagicMock()
    result.scalar_one_or_none.return_value = plan
    result.scalars.return_value.all.return_value = themes
    db = AsyncMock()
    db.execute = AsyncMock(return_value=result)
    db.flush = AsyncMock()
    db.commit = AsyncMock()
    return db


def _db_override(db):
    async def override():
        yield db
    return override


async def _user_override():
    return MOCK_USER_ID


@pytest.mark.asyncio
async def test_list_themes_returns_themes():
    db = _db_for_list(_plan(), [_theme(), _theme("Riesgos")])
    app.dependency_overrides[get_db] = _db_override(db)
    app.dependency_overrides[get_current_user_id] = _user_override
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.get("/api/v1/annual-plan/themes")
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 200
    assert len(r.json()) == 2
    assert r.json()[0]["label"] == "Finanzas"


@pytest.mark.asyncio
async def test_list_themes_404_when_no_plan():
    db = _db_for_list(None, [])
    app.dependency_overrides[get_db] = _db_override(db)
    app.dependency_overrides[get_current_user_id] = _user_override
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.get("/api/v1/annual-plan/themes")
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_patch_theme_404_when_not_owned():
    result = MagicMock()
    result.scalar_one_or_none.return_value = None  # _load_owned_theme no encuentra
    db = AsyncMock()
    db.execute = AsyncMock(return_value=result)
    db.flush = AsyncMock()
    app.dependency_overrides[get_db] = _db_override(db)
    app.dependency_overrides[get_current_user_id] = _user_override
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.patch(f"/api/v1/annual-plan/themes/{uuid.uuid4()}", json={"active": False})
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_create_theme_validation_422():
    db = _db_for_list(_plan(), [])
    app.dependency_overrides[get_db] = _db_override(db)
    app.dependency_overrides[get_current_user_id] = _user_override
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.post("/api/v1/annual-plan/themes",
                             json={"label": "X", "type": "cobertura", "every_n_sessions": 5})
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 422
